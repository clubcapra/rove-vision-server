#!/usr/bin/env python3
import gi
import os
import json
import threading
import time

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')

from gi.repository import Gst, GstRtspServer, GObject

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
        self.rear_cropper = None

        # rearcam with cropping
        self._add_stream(
            "/rearcam",
            self._make_rearcam_pipeline(),
            with_crop=True
        )

        # 360 raw feed
        self._add_stream(
            "/raw360",
            self._make_360_raw_pipeline()
        )

        self.server.attach(None)
        print("RTSP server running at rtsp://<host>:8554/[rearcam|raw360]")

    def _make_rearcam_pipeline(self):
        cam = CAMERAS["rearcam"]
        return f"( v4l2src device={cam['device']} ! " \
               f"video/x-h264, width={cam['width']}, height={cam['height']}, framerate={cam['fps']}/1 ! " \
               f"h264parse ! avdec_h264 ! videoconvert ! " \
               f"videocrop name=rear_cropper top=0 bottom=0 left=0 right=0 ! " \
               f"x264enc tune=zerolatency bitrate={BITRATE_ARDUCAM} speed-preset=ultrafast ! " \
               f"rtph264pay name=pay0 pt=96 )"

    def _make_360_raw_pipeline(self):
        cam = CAMERAS["raw360"]
        return f"( v4l2src device={cam['device']} ! " \
               f"image/jpeg, width={cam['width']}, height={cam['height']}, framerate={cam['fps']}/1 ! " \
               f"jpegdec ! nvvidconv ! " \
               f"video/x-raw(memory:NVMM), format=NV12, width={cam['width']}, height={cam['height']} ! " \
               f"nvv4l2h264enc insert-sps-pps=true maxperf-enable=true bitrate={BITRATE_360} ! " \
               f"rtph264pay name=pay0 pt=96 )"

    def _add_stream(self, mount_point, pipeline_str, with_crop=False):
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline_str)
        factory.set_shared(True)
        if with_crop:
            factory.connect("media-configure", self._on_rearcam_configure)
        self.mounts.add_factory(mount_point, factory)

    def _on_rearcam_configure(self, factory, media):
        def on_prepared(media_obj):
            pipeline = media_obj.get_element()
            self.rear_cropper = pipeline.get_by_name("rear_cropper")
            print("Rearcam pipeline prepared with cropping")
            self._start_crop_monitor()

        media.connect("prepared", on_prepared)

    def _start_crop_monitor(self):
        def loop():
            last = {}
            while True:
                try:
                    with open("crop.json") as f:
                        crop = json.load(f)
                    if crop != last and self.rear_cropper:
                        last = crop
                        for k in ["top", "bottom", "left", "right"]:
                            self.rear_cropper.set_property(k, int(crop.get(k, 0)))
                        print("Crop applied:", crop)
                except Exception as e:
                    pass
                time.sleep(0.1)

        threading.Thread(target=loop, daemon=True).start()

if __name__ == "__main__":
    GObject.threads_init()
    MultiCamRTSPServer()
    loop = GObject.MainLoop()
    loop.run()
