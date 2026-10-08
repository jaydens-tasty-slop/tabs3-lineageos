#!/usr/bin/env python3
"""Generate small synthetic codec fixtures and software decoded pixel references."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(args):
    return subprocess.run(args, check=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "artifacts/device-media-fixtures-v2")
    parser.add_argument("--case", action="append", help="Generate only this named fixture; may be repeated")
    args = parser.parse_args()
    OUTPUT = args.output.resolve()
    if not OUTPUT.is_relative_to(ROOT / "artifacts") or OUTPUT.exists():
        raise ValueError("Use a new fixture directory under artifacts; existing references must remain unchanged")
    OUTPUT.mkdir(parents=True)
    cases = []
    # Constant quadrants make pixel checks deterministic, with no copyrighted media.
    pattern = ("color=c=black:s={width}x{height}:r={fps},"
               "drawbox=x=0:y=0:w=iw/2:h=ih/2:c=red:t=fill,"
               "drawbox=x=iw/2:y=0:w=iw/2:h=ih/2:c=lime:t=fill,"
               "drawbox=x=0:y=ih/2:w=iw/2:h=ih/2:c=blue:t=fill,"
               "drawbox=x=iw/2:y=ih/2:w=iw/2:h=ih/2:c=white:t=fill")
    video = [
        ("avc-baseline-480p", "libx264", 640, 480, 30, ["-profile:v", "baseline", "-preset", "ultrafast"], "mp4"),
        ("avc-main-720p", "libx264", 1280, 720, 30, ["-profile:v", "main", "-preset", "fast"], "mp4"),
        ("avc-high-1080p30", "libx264", 1920, 1080, 30, ["-profile:v", "high", "-preset", "fast"], "mp4"),
        ("avc-high-1080p60", "libx264", 1920, 1080, 60, ["-profile:v", "high", "-preset", "fast"], "mp4"),
        ("avc-high-2160p30", "libx264", 3840, 2160, 30, ["-profile:v", "high", "-preset", "fast"], "mp4"),
        ("hevc-main-480p", "libx265", 640, 480, 30, ["-preset", "fast", "-x265-params", "pools=2:frame-threads=2:log-level=error"], "mp4"),
        ("hevc-main-1080p30", "libx265", 1920, 1080, 30, ["-preset", "fast", "-x265-params", "pools=2:frame-threads=2:log-level=error"], "mp4"),
        ("hevc-main-2160p30", "libx265", 3840, 2160, 30, ["-preset", "fast", "-x265-params", "pools=2:frame-threads=2:log-level=error"], "mp4"),
        ("hevc-main10-720p", "libx265", 1280, 720, 30, ["-profile:v", "main10", "-pix_fmt", "yuv420p10le", "-preset", "fast", "-x265-params", "pools=2:frame-threads=2:log-level=error"], "mp4"),
        ("mpeg4-480p", "mpeg4", 640, 480, 30, ["-q:v", "3"], "mp4"),
        ("mpeg2-480p", "mpeg2video", 640, 480, 30, ["-q:v", "3"], "ts"),
        ("h263-cif", "h263", 352, 288, 30, ["-q:v", "3"], "3gp"),
        ("vp8-480p", "libvpx", 640, 480, 30, ["-deadline", "realtime", "-cpu-used", "4", "-b:v", "1M"], "webm"),
        ("vp9-480p", "libvpx-vp9", 640, 480, 30, ["-deadline", "realtime", "-cpu-used", "4", "-b:v", "1M"], "webm"),
    ]
    audio = (
        ("aac-lc", "aac", "m4a", ["-b:a", "128k"]),
        ("mp3", "libmp3lame", "mp3", ["-b:a", "128k"]),
        ("flac", "flac", "mp4", ["-strict", "-2"]),
        ("vorbis", "libvorbis", "ogg", ["-q:a", "4"]),
        ("opus", "libopus", "ogg", ["-b:a", "128k"]),
    )
    available = {row[0] for row in video} | {row[0] for row in audio}
    requested = set(args.case) if args.case else available
    if len(requested) != len(args.case or requested) or not requested <= available:
        raise ValueError("Unknown or duplicate fixture case")
    for name, encoder, width, height, fps, options, extension in video:
        if name not in requested:
            continue
        file = OUTPUT / (name + "." + extension)
        args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-threads", "2",
                "-f", "lavfi", "-i", pattern.format(width=width, height=height, fps=fps),
                "-frames:v", "30", "-an", "-pix_fmt", "yuv420p", "-c:v", encoder, "-threads", "2", *options,
                "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", str(file)]
        run(args)
        raw = run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(file),
                   "-frames:v", "1", "-vf", "scale=128:128", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]).stdout
        if len(raw) != 128*128*3:
            raise ValueError("Short software reference frame")
        pixels = []
        # GL readback origin is bottom left. Record both the layout and exact reference.
        for x, y in ((32, 96), (96, 96), (32, 32), (96, 32)):
            index = (y*128+x)*3
            pixels.append(list(raw[index:index+3]))
        probe = json.loads(run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(file)]).stdout)
        (OUTPUT / (name + ".ffprobe.json")).write_text(json.dumps(probe, indent=2) + "\n")
        cases.append({"name": name, "file": file.name, "kind": "video", "width": width, "height": height,
                      "fps": fps, "frames": int(probe["streams"][0]["nb_read_frames"]), "reference_pixels_gl_origin": pixels,
                      "pixel_max_error": 12, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "command": args})
        print("Generated " + file.name, flush=True)
    for name, encoder, extension, options in audio:
        if name not in requested:
            continue
        file = OUTPUT / (name + "." + extension)
        args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                "-i", "sine=frequency=440:sample_rate=48000:duration=2", "-ac", "2", "-c:a", encoder, *options, str(file)]
        run(args)
        cases.append({"name": name, "file": file.name, "kind": "audio", "expected_frequency_hz": 440,
                      "duration_seconds": 2, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "command": args})
        print("Generated " + file.name, flush=True)
    vendor = ROOT / "android/device/samsung/gts3l-common/configs/media_codecs.xml"
    xml = ET.parse(vendor).getroot()
    expected = [{"name": node.attrib["name"], "mime": node.attrib.get("type"), "encoder": section.tag == "Encoders",
                 "secure": any(x.attrib.get("name") == "secure-playback" for x in node.findall("Feature"))}
                for section in xml if section.tag in ("Encoders", "Decoders") for node in section.findall("MediaCodec")]
    (OUTPUT / "manifest.json").write_text(json.dumps({
        "scope": "Generated synthetic clear media, 30 frames per video; no DRM license or sustained throughput claim",
        "ffmpeg_version": run(["ffmpeg", "-version"]).stdout.decode(),
        "packages": run(["dpkg-query", "-W", "ffmpeg", "libx264-163", "libx265-199"]).stdout.decode(),
        "expected_vendor_codecs": expected, "vendor_xml_sha256": hashlib.sha256(vendor.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
        "selected_cases": sorted(requested), "cases": cases}, indent=2) + "\n")
    (OUTPUT / "SHA256SUMS").write_text("".join(case["sha256"] + "  " + case["file"] + "\n" for case in cases))
    print("Fixture manifest: " + str(OUTPUT / "manifest.json"), flush=True)


if __name__ == "__main__":
    main()
