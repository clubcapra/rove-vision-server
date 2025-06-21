# Jetson RTSP Multi-Camera Server

This project provides a lightweight GStreamer-based RTSP server for NVIDIA Jetson devices, streaming multiple USB camera feeds (including 360° equirectangular cameras) using hardware acceleration when needed.

## Features

- Serves multiple RTSP streams over `/rearcam`, `/frontcam`, `/raw360`, etc.
- Uses GPU enconding when required, allowing for a smooth stream

## Requirements

- Jetson device with JetPack installed (GStreamer and NVENC should be available).
- Python 3 with GObject introspection:

```bash
sudo apt install python3-gi gir1.2-gst-rtsp-server-1.0
```

## Camera Setup

The script assumes:
- Rear camera (H264) at: `/dev/v4l/by-id/usb-Arducam_*index2`
- Front camera (H264) tbd
- 360 camera (MJPEG) at: `/dev/v4l/by-id/usb-Insta_Insta360_*index0`

Modify the `CAMERAS` dictionary at the top of `rtsp_server_launch.py` if your devices are different.

## Running

Clone and run:

```bash
git clone https://github.com/your-username/jetson-rtsp-server.git
cd jetson-rtsp-server
chmod +x rtsp_server_launch.py
./rtsp_server_launch.py
```

Streams will be available at:

```
rtsp://<your-jetson-ip>:8554/rearcam
rtsp://<your-jetson-ip>:8554/raw360
```

Preview a stream using GStreamer:

```bash
gst-launch-1.0 rtspsrc location=rtsp://<your-jetson-ip>:8554/rearcam latency=0 ! rtph264depay ! avdec_h264 ! videoconvert ! autovideosink
```

## License

MIT
