> **COGNITOHAZARD WARNING:** This README was witten by a real-life human being,
> but this project is otherwise 100% vibecoded and has not been graced by human
> eyes

# Entirely Vibecoded LineageOS 24.0 (Android 17) for the Samsung Galaxy Tab S3

The real credit goes to [awesometic](https://github.com/awesometic) for having a
kernel that brought this device to LineageOS 21. They did the bulk of the work,
this project just brings it over the finish line for LineageOS 24.0.

My contribution was pointing a robot at their work, telling it to get it on latest
android, and doing its bidding (resetting it occasionally).

I've discovered it is quite delightful to funnel investor money to pointless
endeavors via heavily subsidized casino-esque subscriptions. It's like VC for
pointless side projects. Thanks, AI bubble!

## What Works

Pretty much everything I can test.

* WiFi
* Bluetooth
* GPS
* Hardware Acceleration
  * 3D
  * HEVC / H.264 / other codecs
  * Widevine L1 (4k HEVC)
* Fingerprint reader
* Camera (Stability improvements over Awesometic's Android 14 build)
  * 4k30 recording
  * Fix random crashes using the camera
* Microphone
* Headphone
* 4x Speakers
* USB
* S-pen
  * improved palm rejection
* USB OTG

## This Repo

I had the robot try pretty hard to make it easy to build this project yourself.
All you need is Linux and Podman. See [README_LLM.md](README_LLM.md).

Warning: You need a ton of RAM and a huge swapfile to build Android. I have
48gb RAM + 64gb swap on an SSD.

There are some test suites included as well for validating the build.
