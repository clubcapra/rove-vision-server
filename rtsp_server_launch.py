#!/usr/bin/env python3
import gi
import os
import json
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
        self.croppers = {}  # key = cam name, value = videocrop element

        self._add_stream("rearcam", self._make_rearcam_pipeline(), with_crop_name="rearcam")
        self._add_stream("raw360", self._make_raw360_pipeline(), with_crop_name="raw360")

        self.server.attach(None)
        print("RTSP server running at rtsp://<host>:8554/[rearcam|raw360]")

    def _make_rearcam_pipeline(self):
        cam = CAMERAS["rearcam"]
        return f"( v4l2src device={cam['device']} ! " \
               f"video/x-h264, width={cam['width']}, height={cam['height']}, framerate={cam['fps']}/1 ! " \
               f"h264parse ! avdec_h264 ! videoconvert ! " \
               f"videocrop name=rearcam_cropper top=0 bottom=0 left=0 right=0 ! " \
               f"x264enc tune=zerolatency bitrate={BITRATE_ARDUCAM} speed-preset=ultrafast ! " \
               f"rtph264pay name=pay0 pt=96 )"

    def _make_raw360_pipeline(self):
        cam = CAMERAS["raw360"]
        return f"( v4l2src device={cam['device']} ! " \
               f"image/jpeg, width={cam['width']}, height={cam['height']}, framerate={cam['fps']}/1 ! " \
               f"jpegdec ! videocrop name=raw360_cropper top=0 bottom=0 left=0 right=0 ! " \
               f"nvvidconv ! " \
               f"video/x-raw(memory:NVMM), format=NV12, width={cam['width']}, height={cam['height']} ! " \
               f"nvv4l2h264enc insert-sps-pps=true maxperf-enable=true bitrate={BITRATE_360} ! " \
               f"rtph264pay name=pay0 pt=96 )"

    def _add_stream(self, name, pipeline_str, with_crop_name=None):
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline_str)
        factory.set_shared(True)
        if with_crop_name:
            factory.connect("media-configure", lambda f, m: self._on_media_configure(f, m, with_crop_name))
        self.mounts.add_factory(f"/{name}", factory)

    def _on_media_configure(self, factory, media, cam_name):
        def on_prepared(media_obj):
            pipeline = media_obj.get_element()
            cropper = pipeline.get_by_name(f"{cam_name}_cropper")
            if cropper:
                print(f"[INFO] {cam_name} cropper ready")
                self.croppers[cam_name] = cropper
            else:
                print(f"[WARN] No cropper found for {cam_name}")
        media.connect("prepared", on_prepared)

        # Start crop monitor once (only once regardless of camera)
        if not hasattr(self, "crop_monitor_started"):
            self._start_crop_monitor()
            self.crop_monitor_started = True

    def _start_crop_monitor(self):
        def loop():
            print("Crop monitor started. Waiting for crop.json updates...")
            last_data = {}
            while True:
                try:
                    if not os.path.exists(CROP_FILE):
                        time.sleep(0.5)
                        continue

                    with open(CROP_FILE) as f:
                        crop_data = json.load(f)

                    if crop_data != last_data:
                        last_data = crop_data
                        for cam_name, crop_vals in crop_data.items():
                            cropper = self.croppers.get(cam_name)
                            if cropper:
                                for k in ["top", "bottom", "left", "right"]:
                                    cropper.set_property(k, int(crop_vals.get(k, 0)))
                                print(f"[APPLIED] {cam_name} →", crop_vals)
                except Exception as e:
                    print("[ERROR] Crop monitor:", e)

                time.sleep(0.5)

        threading.Thread(target=loop, daemon=True).start()


if __name__ == "__main__":
    GObject.threads_init()
    MultiCamRTSPServer()
    loop = GObject.MainLoop()
    loop.run()
