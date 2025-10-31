FFmpeg 64-bit static Windows build from www.gyan.dev

Version: 8.0-essentials_build-www.gyan.dev

License: GPL v3

Source Code: https://github.com/FFmpeg/FFmpeg/commit/140fd653ae

release-essentials build configuration: 

ARCH                      x86 (generic)
big-endian                no
runtime cpu detection     yes
standalone assembly       yes
x86 assembler             nasm
MMX enabled               yes
MMXEXT enabled            yes
3DNow! enabled            yes
3DNow! extended enabled   yes
SSE enabled               yes
SSSE3 enabled             yes
AESNI enabled             yes
AVX enabled               yes
AVX2 enabled              yes
AVX-512 enabled           yes
AVX-512ICL enabled        yes
XOP enabled               yes
FMA3 enabled              yes
FMA4 enabled              yes
i686 features enabled     yes
CMOV is fast              yes
EBX available             yes
EBP available             yes
debug symbols             yes
strip symbols             yes
optimize for size         no
optimizations             yes
static                    yes
shared                    no
network support           yes
threading support         pthreads
safe bitstream reader     yes
texi2html enabled         no
perl enabled              yes
pod2man enabled           yes
makeinfo enabled          yes
makeinfo supports HTML    yes
xmllint enabled           yes

External libraries:
avisynth                libopencore_amrnb       libvpx
bzlib                   libopencore_amrwb       libwebp
gmp                     libopenjpeg             libx264
gnutls                  libopenmpt              libx265
iconv                   libopus                 libxml2
libaom                  librubberband           libxvid
libass                  libspeex                libzimg
libfontconfig           libsrt                  libzmq
libfreetype             libssh                  lzma
libfribidi              libtheora               mediafoundation
libgme                  libvidstab              openal
libgsm                  libvmaf                 sdl2
libharfbuzz             libvo_amrwbenc          zlib
libmp3lame              libvorbis

External libraries providing hardware acceleration:
amf                     d3d12va                 nvdec
cuda                    dxva2                   nvenc
cuda_llvm               ffnvcodec               vaapi
cuvid                   libmfx
d3d11va                 libvpl

Libraries:
avcodec                 avformat                swscale
avdevice                avutil
avfilter                swresample

Programs:
ffmpeg                  ffplay                  ffprobe

Enabled decoders:
aac                     fraps                   pgmyuv
aac_fixed               frwu                    pgssub
aac_latm                ftr                     pgx
aasc                    g2m                     phm
ac3                     g723_1                  photocd
ac3_fixed               g728                    pictor
acelp_kelvin            g729                    pixlet
adpcm_4xm               gdv                     pjs
adpcm_adx               gem                     png
adpcm_afc               gif                     ppm
adpcm_agm               gremlin_dpcm            prores
adpcm_aica              gsm                     prores_raw
adpcm_argo              gsm_ms                  prosumer
adpcm_ct                h261                    psd
adpcm_dtk               h263                    ptx
adpcm_ea                h263i                   qcelp
adpcm_ea_maxis_xa       h263p                   qdm2
adpcm_ea_r1             h264                    qdmc
adpcm_ea_r2             h264_amf                qdraw
adpcm_ea_r3             h264_cuvid              qoa
adpcm_ea_xas            h264_qsv                qoi
adpcm_g722              hap                     qpeg
adpcm_g726              hca                     qtrle
adpcm_g726le            hcom                    r10k
adpcm_ima_acorn         hdr                     r210
adpcm_ima_alp           hevc                    ra_144
adpcm_ima_amv           hevc_amf                ra_288
adpcm_ima_apc           hevc_cuvid              ralf
adpcm_ima_apm           hevc_qsv                rasc
adpcm_ima_cunning       hnm4_video              rawvideo
adpcm_ima_dat4          hq_hqa                  realtext
adpcm_ima_dk3           hqx                     rka
adpcm_ima_dk4           huffyuv                 rl2
adpcm_ima_ea_eacs       hymt                    roq
adpcm_ima_ea_sead       iac                     roq_dpcm
adpcm_ima_iss           idcin                   rpza
adpcm_ima_moflex        idf                     rscc
adpcm_ima_mtf           iff_ilbm                rtv1
adpcm_ima_oki           ilbc                    rv10
adpcm_ima_qt            imc                     rv20
adpcm_ima_rad           imm4                    rv30
adpcm_ima_smjpeg        imm5                    rv40
adpcm_ima_ssi           indeo2                  rv60
adpcm_ima_wav           indeo3                  s302m
adpcm_ima_ws            indeo4                  sami
adpcm_ima_xbox          indeo5                  sanm
adpcm_ms                interplay_acm           sbc
adpcm_mtaf              interplay_dpcm          scpr
adpcm_psx               interplay_video         screenpresso
adpcm_sanyo             ipu                     sdx2_dpcm
adpcm_sbpro_2           jacosub                 sga
adpcm_sbpro_3           jpeg2000                sgi
adpcm_sbpro_4           jpegls                  sgirle
adpcm_swf               jv                      sheervideo
adpcm_thp               kgv1                    shorten
adpcm_thp_le            kmvc                    simbiosis_imx
adpcm_vima              lagarith                sipr
adpcm_xa                lead                    siren
adpcm_xmd               libaom_av1              smackaud
adpcm_yamaha            libgsm                  smacker
adpcm_zork              libgsm_ms               smc
agm                     libopencore_amrnb       smvjpeg
aic                     libopencore_amrwb       snow
alac                    libopus                 sol_dpcm
alias_pix               libspeex                sonic
als                     libvorbis               sp5x
amrnb                   libvpx_vp8              speedhq
amrwb                   libvpx_vp9              speex
amv                     loco                    srgc
anm                     lscr                    srt
ansi                    m101                    ssa
anull                   mace3                   stl
apac                    mace6                   subrip
ape                     magicyuv                subviewer
apng                    mdec                    subviewer1
aptx                    media100                sunrast
aptx_hd                 metasound               svq1
apv                     microdvd                svq3
arbc                    mimic                   tak
argo                    misc4                   targa
ass                     mjpeg                   targa_y216
asv1                    mjpeg_cuvid             tdsc
asv2                    mjpeg_qsv               text
atrac1                  mjpegb                  theora
atrac3                  mlp                     thp
atrac3al                mmvideo                 tiertexseqvideo
atrac3p                 mobiclip                tiff
atrac3pal               motionpixels            tmv
atrac9                  movtext                 truehd
aura                    mp1                     truemotion1
aura2                   mp1float                truemotion2
av1                     mp2                     truemotion2rt
av1_amf                 mp2float                truespeech
av1_cuvid               mp3                     tscc
av1_qsv                 mp3adu                  tscc2
avrn                    mp3adufloat             tta
avrp                    mp3float                twinvq
avs                     mp3on4                  txd
avui                    mp3on4float             ulti
bethsoftvid             mpc7                    utvideo
bfi                     mpc8                    v210
bink                    mpeg1_cuvid             v210x
binkaudio_dct           mpeg1video              v308
binkaudio_rdft          mpeg2_cuvid             v408
bintext                 mpeg2_qsv               v410
bitpacked               mpeg2video              vb
bmp                     mpeg4                   vble
bmv_audio               mpeg4_cuvid             vbn
bmv_video               mpegvideo               vc1
bonk                    mpl2                    vc1_cuvid
brender_pix             msa1                    vc1_qsv
c93                     mscc                    vc1image
cavs                    msmpeg4v1               vcr1
cbd2_dpcm               msmpeg4v2               vmdaudio
ccaption                msmpeg4v3               vmdvideo
cdgraphics              msnsiren                vmix
cdtoons                 msp2                    vmnc
cdxl                    msrle                   vnull
cfhd                    mss1                    vorbis
cinepak                 mss2                    vp3
clearvideo              msvideo1                vp4
cljr                    mszh                    vp5
cllc                    mts2                    vp6
comfortnoise            mv30                    vp6a
cook                    mvc1                    vp6f
cpia                    mvc2                    vp7
cri                     mvdv                    vp8
cscd                    mvha                    vp8_cuvid
cyuv                    mwsc                    vp8_qsv
dca                     mxpeg                   vp9
dds                     nellymoser              vp9_amf
derf_dpcm               notchlc                 vp9_cuvid
dfa                     nuv                     vp9_qsv
dfpwm                   on2avc                  vplayer
dirac                   opus                    vqa
dnxhd                   osq                     vqc
dolby_e                 paf_audio               vvc
dpx                     paf_video               vvc_qsv
dsd_lsbf                pam                     wady_dpcm
dsd_lsbf_planar         pbm                     wavarc
dsd_msbf                pcm_alaw                wavpack
dsd_msbf_planar         pcm_bluray              wbmp
dsicinaudio             pcm_dvd                 wcmv
dsicinvideo             pcm_f16le               webp
dss_sp                  pcm_f24le               webvtt
dst                     pcm_f32be               wmalossless
dvaudio                 pcm_f32le               wmapro
dvbsub                  pcm_f64be               wmav1
dvdsub                  pcm_f64le               wmav2
dvvideo                 pcm_lxf                 wmavoice
dxa                     pcm_mulaw               wmv1
dxtory                  pcm_s16be               wmv2
dxv                     pcm_s16be_planar        wmv3
eac3                    pcm_s16le               wmv3image
eacmv                   pcm_s16le_planar        wnv1
eamad                   pcm_s24be               wrapped_avframe
eatgq                   pcm_s24daud             ws_snd1
eatgv                   pcm_s24le               xan_dpcm
eatqi                   pcm_s24le_planar        xan_wc3
eightbps                pcm_s32be               xan_wc4
eightsvx_exp            pcm_s32le               xbin
eightsvx_fib            pcm_s32le_planar        xbm
escape124               pcm_s64be               xface
escape130               pcm_s64le               xl
evrc                    pcm_s8                  xma1
exr                     pcm_s8_planar           xma2
fastaudio               pcm_sga                 xpm
ffv1                    pcm_u16be               xsub
ffvhuff                 pcm_u16le               xwd
ffwavesynth             pcm_u24be               y41p
fic                     pcm_u24le               ylc
fits                    pcm_u32be               yop
flac                    pcm_u32le               yuv4
flashsv                 pcm_u8                  zero12v
flashsv2                pcm_vidc                zerocodec
flic                    pcx                     zlib
flv                     pdv                     zmbv
fmvc                    pfm
fourxm                  pgm

Enabled encoders:
a64multi                hevc_d3d12va            pcm_u16le
a64multi5               hevc_mf                 pcm_u24be
aac                     hevc_nvenc              pcm_u24le
aac_mf                  hevc_qsv                pcm_u32be
ac3                     hevc_vaapi              pcm_u32le
ac3_fixed               huffyuv                 pcm_u8
ac3_mf                  jpeg2000                pcm_vidc
adpcm_adx               jpegls                  pcx
adpcm_argo              libaom_av1              pfm
adpcm_g722              libgsm                  pgm
adpcm_g726              libgsm_ms               pgmyuv
adpcm_g726le            libmp3lame              phm
adpcm_ima_alp           libopencore_amrnb       png
adpcm_ima_amv           libopenjpeg             ppm
adpcm_ima_apm           libopus                 prores
adpcm_ima_qt            libspeex                prores_aw
adpcm_ima_ssi           libtheora               prores_ks
adpcm_ima_wav           libvo_amrwbenc          qoi
adpcm_ima_ws            libvorbis               qtrle
adpcm_ms                libvpx_vp8              r10k
adpcm_swf               libvpx_vp9              r210
adpcm_yamaha            libwebp                 ra_144
alac                    libwebp_anim            rawvideo
alias_pix               libx264                 roq
amv                     libx264rgb              roq_dpcm
anull                   libx265                 rpza
apng                    libxvid                 rv10
aptx                    ljpeg                   rv20
aptx_hd                 magicyuv                s302m
ass                     mjpeg                   sbc
asv1                    mjpeg_qsv               sgi
asv2                    mjpeg_vaapi             smc
av1_amf                 mlp                     snow
av1_mf                  movtext                 speedhq
av1_nvenc               mp2                     srt
av1_qsv                 mp2fixed                ssa
av1_vaapi               mp3_mf                  subrip
avrp                    mpeg1video              sunrast
avui                    mpeg2_qsv               svq1
bitpacked               mpeg2_vaapi             targa
bmp                     mpeg2video              text
cfhd                    mpeg4                   tiff
cinepak                 msmpeg4v2               truehd
cljr                    msmpeg4v3               tta
comfortnoise            msrle                   ttml
dca                     msvideo1                utvideo
dfpwm                   nellymoser              v210
dnxhd                   opus                    v308
dpx                     pam                     v408
dvbsub                  pbm                     v410
dvdsub                  pcm_alaw                vbn
dvvideo                 pcm_bluray              vc2
dxv                     pcm_dvd                 vnull
eac3                    pcm_f32be               vorbis
exr                     pcm_f32le               vp8_vaapi
ffv1                    pcm_f64be               vp9_qsv
ffvhuff                 pcm_f64le               vp9_vaapi
fits                    pcm_mulaw               wavpack
flac                    pcm_s16be               wbmp
flashsv                 pcm_s16be_planar        webvtt
flashsv2                pcm_s16le               wmav1
flv                     pcm_s16le_planar        wmav2
g723_1                  pcm_s24be               wmv1
gif                     pcm_s24daud             wmv2
h261                    pcm_s24le               wrapped_avframe
h263                    pcm_s24le_planar        xbm
h263p                   pcm_s32be               xface
h264_amf                pcm_s32le               xsub
h264_mf                 pcm_s32le_planar        xwd
h264_nvenc              pcm_s64be               y41p
h264_qsv                pcm_s64le               yuv4
h264_vaapi              pcm_s8                  zlib
hdr                     pcm_s8_planar           zmbv
hevc_amf                pcm_u16be

Enabled hwaccels:
av1_d3d11va             hevc_nvdec              vc1_nvdec
av1_d3d11va2            hevc_vaapi              vc1_vaapi
av1_d3d12va             mjpeg_nvdec             vp8_nvdec
av1_dxva2               mjpeg_vaapi             vp8_vaapi
av1_nvdec               mpeg1_nvdec             vp9_d3d11va
av1_vaapi               mpeg2_d3d11va           vp9_d3d11va2
h263_vaapi              mpeg2_d3d11va2          vp9_d3d12va
h264_d3d11va            mpeg2_d3d12va           vp9_dxva2
h264_d3d11va2           mpeg2_dxva2             vp9_nvdec
h264_d3d12va            mpeg2_nvdec             vp9_vaapi
h264_dxva2              mpeg2_vaapi             vvc_vaapi
h264_nvdec              mpeg4_nvdec             wmv3_d3d11va
h264_vaapi              mpeg4_vaapi             wmv3_d3d11va2
hevc_d3d11va            vc1_d3d11va             wmv3_d3d12va
hevc_d3d11va2           vc1_d3d11va2            wmv3_dxva2
hevc_d3d12va            vc1_d3d12va             wmv3_nvdec
hevc_dxva2              vc1_dxva2               wmv3_vaapi

Enabled parsers:
aac                     dvdsub                  mpegvideo
aac_latm                evc                     opus
ac3                     ffv1                    png
adx                     flac                    pnm
amr                     ftr                     prores_raw
apv                     g723_1                  qoi
av1                     g729                    rv34
avs2                    gif                     sbc
avs3                    gsm                     sipr
bmp                     h261                    tak
cavsvideo               h263                    vc1
cook                    h264                    vorbis
cri                     hdr                     vp3
dca                     hevc                    vp8
dirac                   ipu                     vp9
dnxhd                   jpeg2000                vvc
dnxuc                   jpegxl                  webp
dolby_e                 misc4                   xbm
dpx                     mjpeg                   xma
dvaudio                 mlp                     xwd
dvbsub                  mpeg4video
dvd_nav                 mpegaudio

Enabled demuxers:
aa                      idcin                   pcm_mulaw
aac                     idf                     pcm_s16be
aax                     iff                     pcm_s16le
ac3                     ifv                     pcm_s24be
ac4                     ilbc                    pcm_s24le
ace                     image2                  pcm_s32be
acm                     image2_alias_pix        pcm_s32le
act                     image2_brender_pix      pcm_s8
adf                     image2pipe              pcm_u16be
adp                     image_bmp_pipe          pcm_u16le
ads                     image_cri_pipe          pcm_u24be
adx                     image_dds_pipe          pcm_u24le
aea                     image_dpx_pipe          pcm_u32be
afc                     image_exr_pipe          pcm_u32le
aiff                    image_gem_pipe          pcm_u8
aix                     image_gif_pipe          pcm_vidc
alp                     image_hdr_pipe          pdv
amr                     image_j2k_pipe          pjs
amrnb                   image_jpeg_pipe         pmp
amrwb                   image_jpegls_pipe       pp_bnk
anm                     image_jpegxl_pipe       pva
apac                    image_pam_pipe          pvf
apc                     image_pbm_pipe          qcp
ape                     image_pcx_pipe          qoa
apm                     image_pfm_pipe          r3d
apng                    image_pgm_pipe          rawvideo
aptx                    image_pgmyuv_pipe       rcwt
aptx_hd                 image_pgx_pipe          realtext
apv                     image_phm_pipe          redspark
aqtitle                 image_photocd_pipe      rka
argo_asf                image_pictor_pipe       rl2
argo_brp                image_png_pipe          rm
argo_cvg                image_ppm_pipe          roq
asf                     image_psd_pipe          rpl
asf_o                   image_qdraw_pipe        rsd
ass                     image_qoi_pipe          rso
ast                     image_sgi_pipe          rtp
au                      image_sunrast_pipe      rtsp
av1                     image_svg_pipe          s337m
avi                     image_tiff_pipe         sami
avisynth                image_vbn_pipe          sap
avr                     image_webp_pipe         sbc
avs                     image_xbm_pipe          sbg
avs2                    image_xpm_pipe          scc
avs3                    image_xwd_pipe          scd
bethsoftvid             imf                     sdns
bfi                     ingenient               sdp
bfstm                   ipmovie                 sdr2
bink                    ipu                     sds
binka                   ircam                   sdx
bintext                 iss                     segafilm
bit                     iv8                     ser
bitpacked               ivf                     sga
bmv                     ivr                     shorten
boa                     jacosub                 siff
bonk                    jpegxl_anim             simbiosis_imx
brstm                   jv                      sln
c93                     kux                     smacker
caf                     kvag                    smjpeg
cavsvideo               laf                     smush
cdg                     lc3                     sol
cdxl                    libgme                  sox
cine                    libopenmpt              spdif
codec2                  live_flv                srt
codec2raw               lmlm4                   stl
concat                  loas                    str
dash                    lrc                     subviewer
data                    luodat                  subviewer1
daud                    lvf                     sup
dcstr                   lxf                     svag
derf                    m4v                     svs
dfa                     matroska                swf
dfpwm                   mca                     tak
dhav                    mcc                     tedcaptions
dirac                   mgsts                   thp
dnxhd                   microdvd                threedostr
dsf                     mjpeg                   tiertexseq
dsicin                  mjpeg_2000              tmv
dss                     mlp                     truehd
dts                     mlv                     tta
dtshd                   mm                      tty
dv                      mmf                     txd
dvbsub                  mods                    ty
dvbtxt                  moflex                  usm
dxa                     mov                     v210
ea                      mp3                     v210x
ea_cdata                mpc                     vag
eac3                    mpc8                    vc1
epaf                    mpegps                  vc1t
evc                     mpegts                  vividas
ffmetadata              mpegtsraw               vivo
filmstrip               mpegvideo               vmd
fits                    mpjpeg                  vobsub
flac                    mpl2                    voc
flic                    mpsub                   vpk
flv                     msf                     vplayer
fourxm                  msnwc_tcp               vqf
frm                     msp                     vvc
fsb                     mtaf                    w64
fwse                    mtv                     wady
g722                    musx                    wav
g723_1                  mv                      wavarc
g726                    mvi                     wc3
g726le                  mxf                     webm_dash_manifest
g728                    mxg                     webvtt
g729                    nc                      wsaud
gdv                     nistsphere              wsd
genh                    nsp                     wsvqa
gif                     nsv                     wtv
gsm                     nut                     wv
gxf                     nuv                     wve
h261                    obu                     xa
h263                    ogg                     xbin
h264                    oma                     xmd
hca                     osq                     xmv
hcom                    paf                     xvag
hevc                    pcm_alaw                xwma
hls                     pcm_f32be               yop
hnm                     pcm_f32le               yuv4mpegpipe
iamf                    pcm_f64be
ico                     pcm_f64le

Enabled muxers:
a64                     h263                    pcm_s16le
ac3                     h264                    pcm_s24be
ac4                     hash                    pcm_s24le
adts                    hds                     pcm_s32be
adx                     hevc                    pcm_s32le
aea                     hls                     pcm_s8
aiff                    iamf                    pcm_u16be
alp                     ico                     pcm_u16le
amr                     ilbc                    pcm_u24be
amv                     image2                  pcm_u24le
apm                     image2pipe              pcm_u32be
apng                    ipod                    pcm_u32le
aptx                    ircam                   pcm_u8
aptx_hd                 ismv                    pcm_vidc
apv                     ivf                     psp
argo_asf                jacosub                 rawvideo
argo_cvg                kvag                    rcwt
asf                     latm                    rm
asf_stream              lc3                     roq
ass                     lrc                     rso
ast                     m4v                     rtp
au                      matroska                rtp_mpegts
avi                     matroska_audio          rtsp
avif                    mcc                     sap
avm2                    md5                     sbc
avs2                    microdvd                scc
avs3                    mjpeg                   segafilm
bit                     mkvtimestamp_v2         segment
caf                     mlp                     smjpeg
cavsvideo               mmf                     smoothstreaming
codec2                  mov                     sox
codec2raw               mp2                     spdif
crc                     mp3                     spx
dash                    mp4                     srt
data                    mpeg1system             stream_segment
daud                    mpeg1vcd                streamhash
dfpwm                   mpeg1video              sup
dirac                   mpeg2dvd                swf
dnxhd                   mpeg2svcd               tee
dts                     mpeg2video              tg2
dv                      mpeg2vob                tgp
eac3                    mpegts                  truehd
evc                     mpjpeg                  tta
f4v                     mxf                     ttml
ffmetadata              mxf_d10                 uncodedframecrc
fifo                    mxf_opatom              vc1
filmstrip               null                    vc1t
fits                    nut                     voc
flac                    obu                     vvc
flv                     oga                     w64
framecrc                ogg                     wav
framehash               ogv                     webm
framemd5                oma                     webm_chunk
g722                    opus                    webm_dash_manifest
g723_1                  pcm_alaw                webp
g726                    pcm_f32be               webvtt
g726le                  pcm_f32le               wsaud
gif                     pcm_f64be               wtv
gsm                     pcm_f64le               wv
gxf                     pcm_mulaw               yuv4mpegpipe
h261                    pcm_s16be

Enabled protocols:
async                   http                    rtmp
cache                   httpproxy               rtmpe
concat                  https                   rtmps
concatf                 icecast                 rtmpt
crypto                  ipfs_gateway            rtmpte
data                    ipns_gateway            rtmpts
fd                      libsrt                  rtp
ffrtmpcrypt             libssh                  srtp
ffrtmphttp              libzmq                  subfile
file                    md5                     tcp
ftp                     mmsh                    tee
gopher                  mmst                    tls
gophers                 pipe                    udp
hls                     prompeg                 udplite

Enabled filters:
a3dscope                datascope               pan
aap                     dblur                   perlin
abench                  dcshift                 perms
abitscope               dctdnoiz                perspective
acompressor             ddagrab                 phase
acontrast               deband                  photosensitivity
acopy                   deblock                 pixdesctest
acrossfade              decimate                pixelize
acrossover              deconvolve              pixscope
acrusher                dedot                   pp7
acue                    deesser                 premultiply
addroi                  deflate                 prewitt
adeclick                deflicker               procamp_vaapi
adeclip                 deinterlace_qsv         pseudocolor
adecorrelate            deinterlace_vaapi       psnr
adelay                  dejudder                pullup
adenorm                 delogo                  qp
aderivative             denoise_vaapi           random
adrawgraph              deshake                 readeia608
adrc                    despill                 readvitc
adynamicequalizer       detelecine              realtime
adynamicsmooth          dialoguenhance          remap
aecho                   dilation                removegrain
aemphasis               displace                removelogo
aeval                   doubleweave             repeatfields
aevalsrc                drawbox                 replaygain
aexciter                drawbox_vaapi           reverse
afade                   drawgraph               rgbashift
afdelaysrc              drawgrid                rgbtestsrc
afftdn                  drawtext                roberts
afftfilt                drmeter                 rotate
afir                    dynaudnorm              rubberband
afireqsrc               earwax                  sab
afirsrc                 ebur128                 scale
aformat                 edgedetect              scale2ref
afreqshift              elbg                    scale_cuda
afwtdn                  entropy                 scale_d3d11
agate                   epx                     scale_qsv
agraphmonitor           eq                      scale_vaapi
ahistogram              equalizer               scdet
aiir                    erosion                 scharr
aintegral               estdif                  scroll
ainterleave             exposure                segment
alatency                extractplanes           select
alimiter                extrastereo             selectivecolor
allpass                 fade                    sendcmd
allrgb                  feedback                separatefields
allyuv                  fftdnoiz                setdar
aloop                   fftfilt                 setfield
alphaextract            field                   setparams
alphamerge              fieldhint               setpts
amerge                  fieldmatch              setrange
ametadata               fieldorder              setsar
amix                    fillborders             settb
amovie                  find_rect               sharpness_vaapi
amplify                 firequalizer            shear
amultiply               flanger                 showcqt
anequalizer             floodfill               showcwt
anlmdn                  format                  showfreqs
anlmf                   fps                     showinfo
anlms                   framepack               showpalette
anoisesrc               framerate               showspatial
anull                   framestep               showspectrum
anullsink               freezedetect            showspectrumpic
anullsrc                freezeframes            showvolume
apad                    fspp                    showwaves
aperms                  fsync                   showwavespic
aphasemeter             gblur                   shuffleframes
aphaser                 geq                     shufflepixels
aphaseshift             gradfun                 shuffleplanes
apsnr                   gradients               sidechaincompress
apsyclip                graphmonitor            sidechaingate
apulsator               grayworld               sidedata
arealtime               greyedge                sierpinski
aresample               guided                  signalstats
areverse                haas                    signature
arls                    haldclut                silencedetect
arnndn                  haldclutsrc             silenceremove
asdr                    hdcd                    sinc
asegment                headphone               sine
aselect                 hflip                   siti
asendcmd                highpass                smartblur
asetnsamples            highshelf               smptebars
asetpts                 hilbert                 smptehdbars
asetrate                histeq                  sobel
asettb                  histogram               spectrumsynth
ashowinfo               hqdn3d                  speechnorm
asidedata               hqx                     split
asisdr                  hstack                  spp
asoftclip               hstack_qsv              sr_amf
aspectralstats          hstack_vaapi            ssim
asplit                  hsvhold                 ssim360
ass                     hsvkey                  stereo3d
astats                  hue                     stereotools
astreamselect           huesaturation           stereowiden
asubboost               hwdownload              streamselect
asubcut                 hwmap                   subtitles
asupercut               hwupload                super2xsai
asuperpass              hwupload_cuda           superequalizer
asuperstop              hysteresis              surround
atadenoise              identity                swaprect
atempo                  idet                    swapuv
atilt                   il                      tblend
atrim                   inflate                 telecine
avectorscope            interlace               testsrc
avgblur                 interleave              testsrc2
avsynctest              join                    thistogram
axcorrelate             kerndeint               threshold
azmq                    kirsch                  thumbnail
backgroundkey           lagfun                  thumbnail_cuda
bandpass                latency                 tile
bandreject              lenscorrection          tiltandshift
bass                    libvmaf                 tiltshelf
bbox                    life                    tinterlace
bench                   limitdiff               tlut2
bilateral               limiter                 tmedian
bilateral_cuda          loop                    tmidequalizer
biquad                  loudnorm                tmix
bitplanenoise           lowpass                 tonemap
blackdetect             lowshelf                tonemap_vaapi
blackframe              lumakey                 tpad
blend                   lut                     transpose
blockdetect             lut1d                   transpose_vaapi
blurdetect              lut2                    treble
bm3d                    lut3d                   tremolo
boxblur                 lutrgb                  trim
bwdif                   lutyuv                  unpremultiply
bwdif_cuda              mandelbrot              unsharp
cas                     maskedclamp             untile
ccrepack                maskedmax               uspp
cellauto                maskedmerge             v360
channelmap              maskedmin               vaguedenoiser
channelsplit            maskedthreshold         varblur
chorus                  maskfun                 vectorscope
chromahold              mcdeint                 vflip
chromakey               mcompand                vfrdet
chromakey_cuda          median                  vibrance
chromanr                mergeplanes             vibrato
chromashift             mestimate               vidstabdetect
ciescope                metadata                vidstabtransform
codecview               midequalizer            vif
color                   minterpolate            vignette
colorbalance            mix                     virtualbass
colorchannelmixer       monochrome              vmafmotion
colorchart              morpho                  volume
colorcontrast           movie                   volumedetect
colorcorrect            mpdecimate              vpp_amf
colordetect             mptestsrc               vpp_qsv
colorhold               msad                    vstack
colorize                multiply                vstack_qsv
colorkey                negate                  vstack_vaapi
colorlevels             nlmeans                 w3fdif
colormap                nnedi                   waveform
colormatrix             noformat                weave
colorspace              noise                   xbr
colorspace_cuda         normalize               xcorrelate
colorspectrum           null                    xfade
colortemperature        nullsink                xmedian
compand                 nullsrc                 xpsnr
compensationdelay       oscilloscope            xstack
concat                  overlay                 xstack_qsv
convolution             overlay_cuda            xstack_vaapi
convolve                overlay_qsv             yadif
copy                    overlay_vaapi           yadif_cuda
corr                    owdenoise               yaepblur
cover_rect              pad                     yuvtestsrc
crop                    pad_cuda                zmq
cropdetect              pad_vaapi               zoneplate
crossfeed               pal100bars              zoompan
crystalizer             pal75bars               zscale
cue                     palettegen
curves                  paletteuse

Enabled bsfs:
aac_adtstoasc           h264_metadata           pcm_rechunk
apv_metadata            h264_mp4toannexb        pgs_frame_merge
av1_frame_merge         h264_redundant_pps      prores_metadata
av1_frame_split         hapqa_extract           remove_extradata
av1_metadata            hevc_metadata           setts
chomp                   hevc_mp4toannexb        showinfo
dca_core                imx_dump_header         smpte436m_to_eia608
dovi_rpu                media100_to_mjpegb      text2movsub
dts2pts                 mjpeg2jpeg              trace_headers
dump_extradata          mjpega_dump_header      truehd_core
dv_error_marker         mov2textsub             vp9_metadata
eac3_core               mpeg2_metadata          vp9_raw_reorder
eia608_to_smpte436m     mpeg4_unpack_bframes    vp9_superframe
evc_frame_merge         noise                   vp9_superframe_split
extract_extradata       null                    vvc_metadata
filter_units            opus_metadata           vvc_mp4toannexb

Enabled indevs:
dshow                   lavfi                   vfwcap
gdigrab                 openal

Enabled outdevs:

release-essentials external libraries' versions: 

AMF v1.4.36-3-gcf4445f
aom v3.12.1-256-g1e5fd6abb3
AviSynthPlus v3.7.5-26-g7ae5d480
ffnvcodec n13.0.19.0-1-gf2fb9b3
freetype VER-2-13-3
fribidi v1.0.16-2-gb28f43b
gsm 1.0.22
harfbuzz 11.4.1-19-gc6153c73
lame 3.100
libass 0.17.4-15-g534a5f8
libgme 0.6.4
libopencore-amrnb 0.1.6
libopencore-amrwb 0.1.6
libssh 0.11.2
libtheora v1.2.0
libwebp v1.6.0-55-g8a2b400
openal-soft latest
openmpt libopenmpt-0.6.24-26-gc9f88bd6b
opus v1.5.2-174-g9c779ed8
rubberband v1.8.1
SDL release-2.32.0-89-g1f21aae24
speex Speex-1.2.1-51-g0589522
srt v1.5.4-37-g5d80411
VAAPI 2.23.0.
vidstab v1.1.1-18-gd9933c1
vmaf v3.0.0-113-g2b2cf9c1
vo-amrwbenc 0.1.3
vorbis v1.3.7-10-g84c02369
VPL 2.15
vpx v1.15.2-100-g40561f514
x264 v0.165.3222
x265 4.1-191-g8f11c33ac
xvid v1.3.7
zeromq 4.3.5
zimg release-3.0.6-208-g1f53009

