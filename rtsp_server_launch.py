#!/usr/bin/env python3

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')

from gi.repository import Gst, GstRtspServer, GObject

# === Configuration ===
CAMERAS = {
    "rearcam": {
        "device": "/dev/v4l/by-id/usb-Arducam_Technology_Co.__Ltd._Arducam_USB_Camera-video-index2",
        "width": 1920,
        "height": 1080,
        "fps": 30
    },
    "frontcam": {
        "device": "/dev/v4l/by-id/usb-Arducam_Technology_Co.__Ltd._Arducam_USB_Camera-video-index0",
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
BITRATE_PLACEHOLDER = 2000000

# === RTSP Server Setup ===
Gst.init(None)

class MultiCamRTSPServer:
    def __init__(self):
        self.server = GstRtspServer.RTSPServer()
        self.mounts = self.server.get_mount_points()

        # Rearcam
        self._add_stream(
            "/rearcam",
            self._make_arducam_pipeline(**CAMERAS["rearcam"])
        )
        # Frontcam
        self._add_stream(
            "/frontcam",
            self._make_arducam_pipeline(**CAMERAS["frontcam"])
        )
        # 360 raw feed
        self._add_stream(
            "/raw360",
            self._make_360_raw_pipeline(CAMERAS["raw360"])
        )

        # Placeholder for processed 360 view (commented out)
        # self._add_stream("/dynamic360", self._make_placeholder_pipeline())

        self.server.attach(None)
        print("RTSP server running at rtsp://<host>:8554/[rearcam|raw360]")

    def _make_arducam_pipeline(self, device, width, height, fps):
        return f"( v4l2src device={device} ! " \
               f"video/x-h264, width={width}, height={height}, framerate={fps}/1 ! " \
               f"h264parse ! " \
               f"rtph264pay config-interval=1 name=pay0 pt=96 )"

    def _make_360_raw_pipeline(self, cam):
        return f"( v4l2src device={cam['device']} ! " \
               f"image/jpeg, width={cam['width']}, height={cam['height']}, framerate={cam['fps']}/1 ! " \
               f"jpegdec ! " \
               f"nvvidconv ! " \
               f"video/x-raw(memory:NVMM), format=NV12, width={cam['width']}, height={cam['height']}, framerate={cam['fps']}/1 ! " \
               f"nvv4l2h264enc insert-sps-pps=true maxperf-enable=true bitrate={BITRATE_360} ! " \
               f"rtph264pay name=pay0 pt=96 )"

    #def _make_360_dynamic_pipeline(slef, cam):

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
