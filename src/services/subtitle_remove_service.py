# -*- coding: utf-8 -*-
"""视频字幕/水印移除服务。

使用STTN模型进行视频修复，支持去除字幕、水印等。
"""

import copy
import os
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import onnxruntime as ort

from utils import logger
from utils.onnx_helper import create_onnx_session


def preprocess_frames(frames: List[np.ndarray]) -> np.ndarray:
    """预处理视频帧，转换为模型输入格式。
    
    Args:
        frames: 输入帧列表，每个帧是numpy数组 (H, W, 3)，值范围[0, 255]
    
    Returns:
        numpy数组，shape: (1, T, 3, H, W)，值范围[-1, 1]
    """
    processed_frames = []
    for frame in frames:
        # 确保是RGB格式
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            # BGR转RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            frame_rgb = frame
        
        # 归一化到[0, 1]
        frame_norm = frame_rgb.astype(np.float32) / 255.0
        
        # 转换为CHW格式 (C, H, W)
        frame_chw = np.transpose(frame_norm, (2, 0, 1))
        processed_frames.append(frame_chw)
    
    # 堆叠为 (T, C, H, W)
    frames_stacked = np.stack(processed_frames, axis=0)
    
    # 添加batch维度: (1, T, C, H, W)
    frames_batch = np.expand_dims(frames_stacked, 0)
    
    # 归一化到[-1, 1]
    frames_batch = frames_batch * 2 - 1
    
    return frames_batch


class SubtitleRemoveService:
    """字幕/水印移除服务类。
    
    使用STTN ONNX模型进行视频修复。
    """
    
    def __init__(self):
        """初始化服务。"""
        self.encoder_session: Optional[ort.InferenceSession] = None
        self.infer_session: Optional[ort.InferenceSession] = None
        self.decoder_session: Optional[ort.InferenceSession] = None
        
        # 模型参数
        self.encoder_batch_size = 10
        self.infer_batch_size = 10
        self.decoder_batch_size = 5
        
        # 模型输入尺寸
        self.model_input_width = 640
        self.model_input_height = 120
        
        # 相邻帧数和参考帧长度
        self.neighbor_stride = 5
        self.ref_length = 10
    
    def load_model(
        self,
        encoder_path: str,
        infer_path: str,
        decoder_path: str,
        neighbor_stride: int = 5,
        ref_length: int = 10
    ) -> None:
        """加载STTN模型。
        
        Args:
            encoder_path: encoder模型路径
            infer_path: infer模型路径
            decoder_path: decoder模型路径
            neighbor_stride: 相邻帧步长
            ref_length: 参考帧长度
        
        Raises:
            FileNotFoundError: 模型文件不存在
            RuntimeError: 模型加载失败
        """
        # 检查模型是否存在
        for path, name in [
            (encoder_path, "encoder"),
            (infer_path, "infer"),
            (decoder_path, "decoder")
        ]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"STTN {name}模型未找到: {path}")
        
        try:
            logger.info("开始加载STTN ONNX模型...")
            
            # 转换为Path对象（create_onnx_session需要Path对象）
            from pathlib import Path
            encoder_path_obj = Path(encoder_path)
            infer_path_obj = Path(infer_path)
            decoder_path_obj = Path(decoder_path)
            
            # 加载三个模型
            self.encoder_session = create_onnx_session(encoder_path_obj)
            self.infer_session = create_onnx_session(infer_path_obj)
            self.decoder_session = create_onnx_session(decoder_path_obj)
            
            # 获取模型期望的batch size
            encoder_input_shape = self.encoder_session.get_inputs()[0].shape
            infer_input_shape = self.infer_session.get_inputs()[0].shape
            decoder_input_shape = self.decoder_session.get_inputs()[0].shape
            
            self.encoder_batch_size = (
                encoder_input_shape[0]
                if isinstance(encoder_input_shape[0], int)
                else 10
            )
            self.infer_batch_size = (
                infer_input_shape[1]
                if len(infer_input_shape) > 1 and isinstance(infer_input_shape[1], int)
                else 10
            )
            self.decoder_batch_size = (
                decoder_input_shape[0]
                if isinstance(decoder_input_shape[0], int)
                else 5
            )
            
            # 更新参数
            self.neighbor_stride = neighbor_stride
            self.ref_length = ref_length
            
            logger.info(
                f"STTN模型加载完成 - "
                f"batch size: encoder={self.encoder_batch_size}, "
                f"infer={self.infer_batch_size}, "
                f"decoder={self.decoder_batch_size}"
            )
            
        except Exception as e:
            logger.error(f"加载STTN模型失败: {e}")
            self.unload_model()
            raise RuntimeError(f"加载STTN模型失败: {e}")
    
    def unload_model(self) -> None:
        """卸载模型释放资源。"""
        self.encoder_session = None
        self.infer_session = None
        self.decoder_session = None
        logger.info("STTN模型已卸载")
    
    def is_model_loaded(self) -> bool:
        """检查模型是否已加载。
        
        Returns:
            模型是否已加载
        """
        return all([
            self.encoder_session is not None,
            self.infer_session is not None,
            self.decoder_session is not None
        ])
    
    def get_ref_index(self, neighbor_ids: List[int], length: int) -> List[int]:
        """采样整个视频的参考帧。
        
        Args:
            neighbor_ids: 邻近帧ID列表
            length: 总帧数
        
        Returns:
            参考帧ID列表
        """
        ref_index = []
        for i in range(0, length, self.ref_length):
            if i not in neighbor_ids:
                ref_index.append(i)
        return ref_index
    
    def inpaint(self, frames: List[np.ndarray]) -> List[np.ndarray]:
        """使用STTN完成空洞填充。
        
        Args:
            frames: 输入帧列表
        
        Returns:
            修复后的帧列表
        
        Raises:
            RuntimeError: 模型未加载或推理失败
        """
        if not self.is_model_loaded():
            raise RuntimeError("STTN模型未加载")
        
        frame_length = len(frames)
        
        # 预处理帧
        feats_batch = preprocess_frames(frames)  # shape: (1, T, 3, H, W)
        feats_np = feats_batch[0]  # (T, 3, H, W)
        
        # 分批通过encoder
        all_feats_encoded = []
        for i in range(0, frame_length, self.encoder_batch_size):
            end_idx = min(i + self.encoder_batch_size, frame_length)
            batch_frames = feats_np[i:end_idx]
            
            # 如果批次不足，填充
            if len(batch_frames) < self.encoder_batch_size:
                padding_needed = self.encoder_batch_size - len(batch_frames)
                padding = np.repeat(batch_frames[-1:], padding_needed, axis=0)
                batch_frames = np.concatenate([batch_frames, padding], axis=0)
            
            encoder_outputs = self.encoder_session.run(
                None,
                {'frames': batch_frames}
            )
            batch_feats_encoded = encoder_outputs[0]
            all_feats_encoded.append(batch_feats_encoded[:end_idx - i])
        
        feats_encoded = np.concatenate(all_feats_encoded, axis=0)  # (T, C, feat_h, feat_w)
        
        # 调整特征形状以匹配infer输入: (1, T, C, H, W)
        feats_encoded = np.expand_dims(feats_encoded, 0)
        
        # 初始化存储
        comp_frames = [None] * frame_length
        
        # 在设定的邻居帧步幅内循环处理视频
        for f in range(0, frame_length, self.neighbor_stride):
            # 计算邻近帧的ID
            neighbor_ids = [
                i for i in range(
                    max(0, f - self.neighbor_stride),
                    min(frame_length, f + self.neighbor_stride + 1)
                )
            ]
            # 获取参考帧的索引
            ref_ids = self.get_ref_index(neighbor_ids, frame_length)
            
            # 选择特征: neighbor_ids + ref_ids
            all_ids = neighbor_ids + ref_ids
            selected_feats = feats_encoded[0, all_ids, :, :, :]  # (num_all_frames, C, H, W)
            
            # 通过infer
            selected_feats_batch = np.expand_dims(selected_feats, 0)  # (1, num_all_frames, C, H, W)
            
            # 如果帧数超过infer的batch size，需要分批处理
            num_all_frames = len(all_ids)
            if num_all_frames > self.infer_batch_size:
                # 分批处理infer
                infer_outputs_list = []
                for i in range(0, num_all_frames, self.infer_batch_size):
                    end_idx = min(i + self.infer_batch_size, num_all_frames)
                    batch_feats = selected_feats[i:end_idx]
                    
                    # 填充到固定大小
                    if len(batch_feats) < self.infer_batch_size:
                        padding_needed = self.infer_batch_size - len(batch_feats)
                        padding = np.repeat(batch_feats[-1:], padding_needed, axis=0)
                        batch_feats = np.concatenate([batch_feats, padding], axis=0)
                    
                    batch_feats_batch = np.expand_dims(batch_feats, 0)
                    
                    infer_outputs = self.infer_session.run(
                        None,
                        {'features': batch_feats_batch}
                    )
                    infer_outputs_list.append(infer_outputs[0][:end_idx - i])
                
                pred_feat = np.concatenate(infer_outputs_list, axis=0)
            else:
                # 如果帧数不足，填充
                if num_all_frames < self.infer_batch_size:
                    padding_needed = self.infer_batch_size - num_all_frames
                    padding = np.repeat(selected_feats[-1:], padding_needed, axis=0)
                    selected_feats_batch = np.expand_dims(
                        np.concatenate([selected_feats, padding], axis=0), 0
                    )
                
                infer_outputs = self.infer_session.run(
                    None,
                    {'features': selected_feats_batch}
                )
                pred_feat = infer_outputs[0]  # (infer_batch_size, C, H, W)
                pred_feat = pred_feat[:num_all_frames]
            
            # 只使用邻近帧的预测
            pred_feat_neighbor = pred_feat[:len(neighbor_ids), :, :, :]
            
            # 分批通过decoder
            all_pred_imgs = []
            for i in range(0, len(neighbor_ids), self.decoder_batch_size):
                end_idx = min(i + self.decoder_batch_size, len(neighbor_ids))
                batch_feats = pred_feat_neighbor[i:end_idx]
                
                # 填充到固定大小
                if len(batch_feats) < self.decoder_batch_size:
                    padding_needed = self.decoder_batch_size - len(batch_feats)
                    padding = np.repeat(batch_feats[-1:], padding_needed, axis=0)
                    batch_feats = np.concatenate([batch_feats, padding], axis=0)
                
                decoder_outputs = self.decoder_session.run(
                    None,
                    {'pred_features': batch_feats}
                )
                batch_pred_img = decoder_outputs[0]
                all_pred_imgs.append(batch_pred_img[:end_idx - i])
            
            pred_img = np.concatenate(all_pred_imgs, axis=0)  # (num_neighbor, 3, H, W)
            
            # 后处理
            pred_img = np.tanh(pred_img)
            pred_img = (pred_img + 1) / 2
            pred_img = np.transpose(pred_img, (0, 2, 3, 1)) * 255  # (num_neighbor, H, W, 3)
            
            # 遍历邻近帧
            for i in range(len(neighbor_ids)):
                idx = neighbor_ids[i]
                img = np.array(pred_img[i]).astype(np.uint8)
                if comp_frames[idx] is None:
                    comp_frames[idx] = img
                else:
                    # 混合以提高质量
                    comp_frames[idx] = (
                        comp_frames[idx].astype(np.float32) * 0.5 +
                        img.astype(np.float32) * 0.5
                    )
        
        return comp_frames
    
    @staticmethod
    def get_inpaint_area_by_mask(
        H: int,
        h: int,
        mask: np.ndarray
    ) -> List[Tuple[int, int]]:
        """获取字幕去除区域。
        
        改进版：扫描整个图像高度，找出所有包含mask的区域。
        
        Args:
            H: 图像高度
            h: 分割高度（每个处理块的高度）
            mask: 遮罩图像
        
        Returns:
            需要修复的区域列表，每个元素为(from_H, to_H)
        """
        inpaint_area = []
        
        # 首先找出所有包含mask的行
        row_has_mask = []
        for y in range(H):
            if np.sum(mask[y, :]) > 0:
                row_has_mask.append(y)
        
        if not row_has_mask:
            return inpaint_area
        
        # 找出连续的mask区域段
        segments = []
        start = row_has_mask[0]
        end = row_has_mask[0]
        
        for y in row_has_mask[1:]:
            if y <= end + 1:  # 连续或相邻
                end = y
            else:  # 新的段
                segments.append((start, end + 1))
                start = y
                end = y
        segments.append((start, end + 1))  # 添加最后一段
        
        # 将每个段扩展到处理块大小，并分割成多个块
        for seg_start, seg_end in segments:
            seg_height = seg_end - seg_start
            
            if seg_height <= h:
                # 区域小于或等于一个块，居中扩展到块大小
                center = (seg_start + seg_end) // 2
                from_H = max(0, center - h // 2)
                to_H = min(H, from_H + h)
                if to_H - from_H < h:
                    from_H = max(0, to_H - h)
                
                if (from_H, to_H) not in inpaint_area:
                    inpaint_area.append((from_H, to_H))
            else:
                # 区域大于一个块，分割成多个块
                current = seg_start
                while current < seg_end:
                    from_H = current
                    to_H = min(seg_end, current + h)
                    
                    # 确保块大小为 h
                    if to_H - from_H < h:
                        from_H = max(0, to_H - h)
                    
                    if (from_H, to_H) not in inpaint_area:
                        inpaint_area.append((from_H, to_H))
                    
                    current += h
        
        # 按起始位置排序
        inpaint_area.sort(key=lambda x: x[0])
        
        return inpaint_area
    
    def process_video_streaming(
        self,
        video_path: str,
        output_path: str,
        mask_callback: callable,
        fps: float,
        progress_callback: Optional[callable] = None,
        batch_size: int = 10
    ) -> bool:
        """流式处理视频帧，支持按时间动态创建mask。
        
        Args:
            video_path: 输入视频路径
            output_path: 输出视频路径（临时无音频文件）
            mask_callback: mask创建回调，参数为(height, width, current_time)，返回mask数组
            fps: 视频帧率
            progress_callback: 进度回调函数，参数为(current, total)
            batch_size: 每批处理的帧数，越小内存占用越低
        
        Returns:
            处理是否成功
        
        Raises:
            RuntimeError: 模型未加载或处理失败
        """
        if not self.is_model_loaded():
            raise RuntimeError("STTN模型未加载")
        
        # 打开视频获取信息
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        W_ori = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        H_ori = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # 创建视频写入器
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (W_ori, H_ori))
        
        # 用于缓存mask对应的inpaint_area
        split_h = int(W_ori * 3 / 16)
        last_mask_hash = None
        inpaint_area = []
        mask = None
        
        processed_count = 0
        
        while True:
            # 记录当前批次的起始帧号
            batch_start_frame = processed_count
            
            # 读取一批帧
            batch_frames = []
            batch_times = []
            for i in range(batch_size):
                ret, frame = cap.read()
                if not ret:
                    break
                batch_frames.append(frame)
                # 计算当前帧的时间
                frame_time = (batch_start_frame + i) / fps
                batch_times.append(frame_time)
            
            if not batch_frames:
                break
            
            # 使用批次中间帧的时间来获取mask（同一批次使用相同mask）
            mid_time = batch_times[len(batch_times) // 2]
            current_mask = mask_callback(H_ori, W_ori, mid_time)
            
            # 处理mask
            if len(current_mask.shape) == 3:
                current_mask = current_mask[:, :, 0]
            
            _, mask_binary = cv2.threshold(current_mask, 127, 1, cv2.THRESH_BINARY)
            
            # 检查mask是否有变化（通过计算和值来判断）
            mask_hash = np.sum(mask_binary)
            
            if mask_hash != last_mask_hash:
                # mask有变化，重新计算inpaint_area
                mask = mask_binary[:, :, None]
                inpaint_area = self.get_inpaint_area_by_mask(H_ori, split_h, mask)
                last_mask_hash = mask_hash
                if inpaint_area:
                    logger.info(f"时间 {mid_time:.1f}s: mask变化，{len(inpaint_area)} 个区域需要修复")
            
            if not inpaint_area:
                # 没有需要修复的区域，直接写入原帧
                for frame in batch_frames:
                    out.write(frame)
            else:
                # 处理这批帧的每个区域
                for k, (from_H, to_H) in enumerate(inpaint_area):
                    # 提取并缩放这批帧的对应区域
                    frames_scaled = []
                    for frame in batch_frames:
                        image_crop = frame[from_H:to_H, :, :]
                        image_resize = cv2.resize(
                            image_crop,
                            (self.model_input_width, self.model_input_height)
                        )
                        frames_scaled.append(image_resize)
                    
                    # 修复这个区域
                    comps = self.inpaint(frames_scaled)
                    
                    # 将修复结果合成回原帧
                    for j, frame in enumerate(batch_frames):
                        comp = cv2.resize(comps[j], (W_ori, split_h))
                        comp = cv2.cvtColor(np.array(comp).astype(np.uint8), cv2.COLOR_BGR2RGB)
                        mask_area = mask[from_H:to_H, :]
                        frame[from_H:to_H, :, :] = (
                            mask_area * comp +
                            (1 - mask_area) * frame[from_H:to_H, :, :]
                        )
                    
                    # 清理临时变量
                    del frames_scaled
                    del comps
                
                # 写入处理后的帧
                for frame in batch_frames:
                    out.write(frame)
            
            processed_count += len(batch_frames)
            
            if progress_callback:
                progress_callback(processed_count, total_frames)
            
            # 清理这批帧
            del batch_frames
        
        cap.release()
        out.release()
        
        logger.info(f"视频处理完成，共 {processed_count} 帧")
        return True

