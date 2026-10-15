import pytest


@pytest.mark.quick
def test_platform_smoke(run_probe):
    run_probe("device_smoke.py")


@pytest.mark.quick
def test_media_framework_and_generated_decode(run_probe, media_probe_app):
    run_probe("device_media_probe.py", "--suite", "all")


@pytest.mark.quick
def test_vulkan_compute(run_probe):
    run_probe("device_vulkan_probe.py")


@pytest.mark.full
def test_all_generated_clear_codecs(run_probe, media_probe_app):
    run_probe("device_media_probe.py", "--suite", "decode", "--fixtures",
              "artifacts/device-media-fixtures-full-v1", timeout=1800)


@pytest.mark.full
def test_hardware_encoders(run_probe, media_probe_app):
    run_probe("device_media_probe.py", "--suite", "encode", "--fixtures",
              "artifacts/device-media-fixtures-full-v1", timeout=900)


@pytest.mark.full
def test_widevine_l1_secure_hevc(run_probe, media_probe_app):
    run_probe("device_media_probe.py", "--suite", "secure-decode", "--fixtures",
              "artifacts/device-media-fixtures-full-v1",
              "--case", "hevc-main-480p", "--case", "hevc-main-1080p30",
              "--case", "hevc-main10-720p", timeout=900)


@pytest.mark.full
def test_camera_microphone_and_sensors(run_probe):
    run_probe("device_io_probe.py", "--suite", "all", timeout=900)


@pytest.mark.full
def test_app_network_permission_and_uid_accounting(run_probe):
    run_probe("device_usb_probe.py", "--expected-sdk", "37", "--transport", "usb",
              timeout=300)


@pytest.mark.full
@pytest.mark.parametrize("capture,close", [
    ("preview", "direct"),
    ("preview", "drain"),
    ("jpeg", "direct"),
    ("jpeg_idle", "drain"),
])
def test_camera2_lifecycle(run_probe, camera_probe_app, capture, close):
    run_probe("device_camera_control_regression.py", "--cycles", "2",
              "--capture-choice", capture, "--close-mode", close,
              "--camera-id", "both", timeout=600)


@pytest.mark.full
def test_framework_stability_window(run_probe):
    run_probe("device_stability.py", "--seconds", "120", timeout=180)


@pytest.mark.browser
def test_fdroid_inventory_app(run_probe):
    run_probe("device_fdroid_validation.py", "--phase", "inventory", timeout=300)


@pytest.mark.browser
def test_bounded_fdroid_stress(run_probe):
    run_probe("device_fdroid_validation.py", "--phase", "stress",
              "--minutes", "1", "--threads", "2", timeout=300)


@pytest.mark.browser
def test_fennec_known_transparent_video_canvas_limit(run_probe):
    run_probe("device_fdroid_validation.py", "--phase", "browser",
              "--browser-suite", "fixture",
              "--accept-fennec-transparent-video-canvas", timeout=600)


@pytest.mark.browser
def test_browser_hardware_acceleration_fixture(run_probe):
    run_probe("device_fdroid_validation.py", "--phase", "browser",
              "--browser-package", "de.baumann.browser",
              "--browser-suite", "fixture", timeout=600)


@pytest.mark.browser
def test_browser_public_https(run_probe):
    run_probe("device_fdroid_validation.py", "--phase", "browser",
              "--browser-package", "de.baumann.browser",
              "--browser-suite", "full", timeout=900)


@pytest.mark.browser
def test_warm_app_ui_transitions(run_probe):
    run_probe("device_ui_performance.py", "--phase", "switch", "--rounds", "4",
              timeout=900)
