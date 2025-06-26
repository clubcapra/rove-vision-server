#!/usr/bin/env python3
import gi
import json
import os
import threading
import time

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GObject

CROP_FILE = "crop.json"

CAMERAS = {
    "rearcam": {
        "device": "/dev/v4l/by-id/usb-Arducam_Technology_Co.__Ltd._Arducam_USB_Camera-video-index2",
        "width": 1920,
        "height": 1080,
        "fps": 30
    },
    "raw360": {
        "device": "/dev/v4l/by-id/usb-Insta_Insta360_X4_0001-video-index0",
        "width": 2880,
        "height": 1440,
        "fps": 30
    }
}

BITRATE_ARDUCAM = 4000000
BITRATE_360 = 8000000

Gst.init(None)

class MultiCamRTSPServer:
    def __init__(self):
        self.server = GstRtspServer.RTSPServer()
        self.mounts = self.server.get_mount_points()

        # Rearcam: unchanged
        self._add_stream("/rearcam", self._make_arducam_pipeline(**CAMERAS["rearcam"]))

        # Raw360 with cropping support
        self._add_crop_stream("/raw360", self._make_360_crop_pipeline(CAMERAS["raw360"]))

        self.server.attach(None)
        print("RTSP server running at rtsp://<host>:8554/[rearcam|raw360]")

    def _make_arducam_pipeline(self, device, width, height, fps):
        return f"( v4l2src device={device} ! " \
               f"video/x-h264, width={width}, height={height}, framerate={fps}/1 ! " \
               f"h264parse ! rtph264pay config-interval=1 name=pay0 pt=96 )"

    def _make_360_crop_pipeline(self, cam):
        return f"( v4l2src device={cam['device']} ! image/jpeg, width={cam['width']}, height={cam['height']}, framerate={cam['fps']}/1 ! " \
               f"jpegdec ! videocrop name=cropper top=0 bottom=0 left=0 right=0 ! " \
               f"nvvidconv ! video/x-raw(memory:NVMM), format=NV12, width={cam['width']}, height={cam['height']} ! " \
               f"nvv4l2h264enc insert-sps-pps=true maxperf-enable=true bitrate={BITRATE_360} ! rtph264pay name=pay0 pt=96 )"

    def _add_crop_stream(self, mount_point, pipeline_str):
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline_str)
        factory.set_shared(True)
        factory.connect("media-configure", self._on_crop_media_configure)
        self.mounts.add_factory(mount_point, factory)

    def _on_crop_media_configure(self, factory, media):
        def on_prepared(media_obj):
            pipeline = media_obj.get_element()
            cropper = pipeline.get_by_name("cropper")
            self._start_crop_monitor(cropper)
        media.connect("prepared", on_prepared)

    def _start_crop_monitor(self, cropper):
        def crop_loop():
            print("Crop monitor running for raw360 stream...")
            last_crop = {}
            while True:
                try:
                    if not os.path.exists(CROP_FILE):
                        time.sleep(0.5)
                        continue
                    with open(CROP_FILE) as f:
                        crop = json.load(f)
                    if crop != last_crop:
                        for key in ["top", "bottom", "left", "right"]:
                            if key in crop:
                                cropper.set_property(key, int(crop[key]))
                        last_crop = crop
                        print("Applied crop:", crop)
                except Exception as e:
                    print("Crop error:", e)
                time.sleep(0.5)
        threading.Thread(target=crop_loop, daemon=True).start()


if __name__ == '__main__':
    GObject.threads_init()
    MultiCamRTSPServer()
    loop = GObject.MainLoop()
    loop.run()
