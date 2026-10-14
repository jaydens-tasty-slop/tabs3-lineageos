#!/usr/bin/env python3
"""Generate longer moving AVC/HEVC clips with exact sampled-frame references."""
import argparse
import hashlib
import json
import pathlib
import subprocess

from generate_media_fixtures import ROOT, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--duration", type=int, default=20)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "artifacts") or output.exists() or not 10 <= args.duration <= 60:
        raise ValueError("Use a new artifacts directory and 10–60 seconds per clip")
    output.mkdir(parents=True)
    cases = []
    specifications = (
        ("avc-high-1080p60-moving", "libx264", 1920, 1080, 60, ("-profile:v", "high", "-preset", "fast")),
        ("avc-high-2160p30-moving", "libx264", 3840, 2160, 30, ("-profile:v", "high", "-preset", "fast")),
        ("hevc-main-1080p60-moving", "libx265", 1920, 1080, 60, ("-preset", "fast", "-x265-params", "pools=2:frame-threads=2:log-level=error")),
        ("hevc-main-2160p30-moving", "libx265", 3840, 2160, 30, ("-preset", "fast", "-x265-params", "pools=2:frame-threads=2:log-level=error")),
        ("hevc-main10-1080p30-moving", "libx265", 1920, 1080, 30, ("-profile:v", "main10", "-pix_fmt", "yuv420p10le", "-preset", "fast", "-x265-params", "pools=2:frame-threads=2:log-level=error")),
    )
    for name, encoder, width, height, fps, options in specifications:
        count = args.duration * fps
        file = output / (name + ".mp4")
        filters = (
            "drawbox=x=iw*.15:y=ih*.15:w=iw*.2:h=ih*.2:c=red:t=fill,"
            "drawbox=x=iw*.65:y=ih*.15:w=iw*.2:h=ih*.2:c=lime:t=fill,"
            "drawbox=x=iw*.15:y=ih*.65:w=iw*.2:h=ih*.2:c=blue:t=fill,"
            "drawbox=x=iw*.65:y=ih*.65:w=iw*.2:h=ih*.2:c=white:t=fill,"
            "drawbox=x=iw*.4:y=ih*.4:w=iw*.2:h=ih*.2:c=black:t=fill,"
            "drawbox=x=iw*.4:y=ih*.4:w=iw*.2:h=ih*.2:c=white:t=fill:enable='lt(mod(n,90),30)',"
            "drawbox=x=iw*.4:y=ih*.4:w=iw*.2:h=ih*.2:c=gray:t=fill:enable='between(mod(n,90),30,59)'"
        )
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                   "-i", "testsrc2=s=%dx%d:r=%d" % (width, height, fps), "-vf", filters,
                   "-frames:v", str(count), "-an", "-pix_fmt", "yuv420p", "-c:v", encoder,
                   "-threads", "2", *options, "-colorspace", "bt709", "-color_primaries", "bt709",
                   "-color_trc", "bt709", "-color_range", "tv", str(file)]
        run(command)
        reference_command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(file),
                             "-vf", "scale=128:128", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
        raw = run(reference_command).stdout
        frame_bytes = 128 * 128 * 3
        if len(raw) != count * frame_bytes:
            raise ValueError("Independent decoder returned the wrong frame count")
        references = []
        for number in sorted({1, 2, 3, *range(30, count + 1, 30)}):
            frame = memoryview(raw)[(number-1)*frame_bytes:number*frame_bytes]
            pixels = [list(frame[(y*128+x)*3:(y*128+x)*3+3]) for x,y in ((32,96),(96,96),(32,32),(96,32))]
            references.append({"frame": number, "pixels": pixels, "center_pixel": list(frame[(63*128+64)*3:(63*128+64)*3+3])})
        probe = json.loads(run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(file)]).stdout)
        (output / (name + ".ffprobe.json")).write_text(json.dumps(probe, indent=2) + "\n")
        cases.append({"name": name, "file": file.name, "kind": "video", "width": width, "height": height,
                      "fps": fps, "frames": count, "duration_seconds": args.duration,
                      "reference_pixels_gl_origin": references[0]["pixels"], "reference_frames": references,
                      "pixel_max_error": 12, "minimum_processing_fps": fps,
                      "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "command": command,
                      "reference_command": reference_command})
        print("Generated " + file.name + ": " + str(count) + " independently decoded frames", flush=True)
    (output / "manifest.json").write_text(json.dumps({"cases": cases,
        "scope": "Moving generated media with static color patches and a frame-dependent center marker. Decode throughput includes SurfaceTexture rendering; no A/V sync, HDR or protected-playback claim.",
        "ffmpeg_version": run(["ffmpeg", "-version"]).stdout.decode()}, indent=2) + "\n")
    (output / "SHA256SUMS").write_text("".join(c["sha256"] + "  " + c["file"] + "\n" for c in cases))
    print("Stress fixture manifest: " + str(output / "manifest.json"), flush=True)


if __name__ == "__main__":
    main()
