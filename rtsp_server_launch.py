#!/usr/bin/env python3

import gi
import cv2
import numpy as np
import time
import threading
import queue

import pyzed.sl as sl

gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
gi.require_version('GstRtspServer', '1.0')

from gi.repository import Gst, GstApp, GstRtspServer, GObject

Gst.init(None)

# === Configuration ===
CAMERAS = {
    "rearcam": {
        "device": "/dev/video6",
        "width": 1920,
        "height": 1080,
        "fps": 30
    },
    "frontcam": {
        "device": "/dev/video2",
        "width": 1920,
        "height": 1080,
        "fps": 30
    },
    "raw360": {
        "device": "/dev/insta",
        "width": 2880,
        "height": 1440,
        "fps": 30
    }
}
BITRATE_ARDUCAM = 4000000
BITRATE_360 = 8000000
BITRATE_PLACEHOLDER = 2000000

# === ZED RTSP Factory with Multithreading ===
class ZEDRtspFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, width=1280, height=720, fps=30):
        super().__init__()
        self.width = width
        self.height = height
        self.fps = fps
        self.duration = Gst.util_uint64_scale_int(1, Gst.SECOND, fps)
        self.number_frames = 0
        self.set_shared(True)

        self.frame_queue = queue.Queue(maxsize=5)
        self.running = True
        self.appsrc = None

        # Initialize ZED camera
        self.zed = sl.Camera()
        init_params = sl.InitParameters()
        init_params.camera_resolution = sl.RESOLUTION.HD720
        init_params.camera_fps = self.fps
        status = self.zed.open(init_params)
        if status != sl.ERROR_CODE.SUCCESS:
            print("❌ ZED camera failed to open:", status)
            self.zed = None
        else:
            print("✅ ZED camera initialized")
            self.image = sl.Mat()
            self.capture_thread = threading.Thread(target=self._zed_capture_loop, daemon=True)
            self.capture_thread.start()

    def _zed_capture_loop(self):
        while self.running and self.zed:
            if self.zed.grab() == sl.ERROR_CODE.SUCCESS:
                self.zed.retrieve_image(self.image, sl.VIEW.LEFT)
                raw = self.image.get_data()
                frame = raw[:, :self.width, :3].copy()
                try:
                    self.frame_queue.put(frame, timeout=1)
                except queue.Full:
                    pass  # Drop frame if queue is full
            else:
                time.sleep(0.01)

    def do_create_element(self, url):
        if not self.zed:
            return None
        pipeline = f"""
        appsrc name=source is-live=true block=true format=TIME caps=video/x-raw,format=BGR,width={self.width},height={self.height},framerate={self.fps}/1 !
        videoconvert !
        x264enc tune=zerolatency bitrate=4000 speed-preset=ultrafast !
        rtph264pay config-interval=1 name=pay0 pt=96
        """
        return Gst.parse_launch(pipeline)

    def do_configure(self, rtsp_media):
        self.appsrc = rtsp_media.get_element().get_child_by_name("source")
        if self.appsrc:
            self.appsrc.connect("need-data", self.on_need_data)

    def on_need_data(self, src, length):
        try:
            frame = self.frame_queue.get(timeout=1)
        except queue.Empty:
            return

        data = frame.tobytes()
        buf = Gst.Buffer.new_allocate(None, len(data), None)
        buf.fill(0, data)
        buf.duration = self.duration
        timestamp = self.number_frames * self.duration
        buf.pts = buf.dts = int(timestamp)
        self.number_frames += 1

        retval = self.appsrc.emit("push-buffer", buf)
        if retval != Gst.FlowReturn.OK:
            print(f"Push buffer error: {retval}")

    def __del__(self):
        self.running = False
        if self.capture_thread.is_alive():
            self.capture_thread.join()

# === RTSP Server ===
class MultiCamRTSPServer:
    def __init__(self):
        self.server = GstRtspServer.RTSPServer()
        self.mounts = self.server.get_mount_points()

        self._add_stream("/rearcam", self._make_arducam_pipeline(**CAMERAS["rearcam"]))
        self._add_stream("/frontcam", self._make_arducam_pipeline(**CAMERAS["frontcam"]))
        self._add_stream("/raw360", self._make_360_raw_pipeline(CAMERAS["raw360"]))

        zed_factory = ZEDRtspFactory()
        self.mounts.add_factory("/zedmini", zed_factory)

        self.server.attach(None)
        print("RTSP server running at rtsp://<host>:8554/[frontcam|rearcam|raw360|zedmini]")

    def _make_arducam_pipeline(self, device, width, height, fps):
        return f"( v4l2src device={device} ! " \
               f"video/x-h264, width={width}, height={height}, framerate={fps}/1 ! " \
               f"h264parse ! rtph264pay config-interval=1 name=pay0 pt=96 )"

    def _make_360_raw_pipeline(self, cam):
        return f"( v4l2src device={cam['device']} ! " \
               f"image/jpeg, width={cam['width']}, height={cam['height']}, framerate={cam['fps']}/1 ! " \
               f"jpegdec ! nvvidconv ! " \
               f"video/x-raw(memory:NVMM), format=NV12, width={cam['width']}, height={cam['height']}, framerate={cam['fps']}/1 ! " \
               f"nvv4l2h264enc insert-sps-pps=true maxperf-enable=true bitrate={BITRATE_360} ! " \
               f"rtph264pay name=pay0 pt=96 )"

    def _add_stream(self, mount_point, pipeline_str):
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(pipeline_str)
        factory.set_shared(True)
        self.mounts.add_factory(mount_point, factory)

# === Entry Point ===
if __name__ == '__main__':
    GObject.threads_init()
    MultiCamRTSPServer()
    loop = GObject.MainLoop()
    loop.run()
