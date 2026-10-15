## Decisions
Keep the existing continuous cosine pulse curve. Fix sampling/transport selection rather than adding interpolation between two already sparse samples. Native pulse is preferred; primary colors are brightness-scaled only when the hardware mode has no brightness control.

For known HydroShift II and UNI FAN TL wireless devices, verify the bridge replay-safe capability, upload a periodic loop sampled near 30 FPS (maximum160 frames /48000 raw bytes), then let firmware play it. The final-to-first transition follows the same continuous cosine cycle. Changes/reconnects re-upload; static/off sends replace the loop. Unknown/older bridges keep SDK fallback.

The wireless packet cache already stores complete uploads. Drift recovery must resend those packets and retain their original effect index, not synthesize a static last frame. Fan PWM transactions keep existing locking and cooling settings.

Software USB fallback is rate-limited per device to30 FPS; I2C/RF/unknown remain2 FPS. Worker ticks at up to30 Hz while animated; native modes incur no repeated writes.

The reference AORUS RTX 5080 built-in Pulse remained visibly stepped in user testing. Use Direct software pulse at up to30 FPS only for this tested GPU on its dedicated NVIDIA I2C adapter with Direct capability. Unrecognized I2C/SMBus controllers retain their conservative profile. Twenty acknowledged Direct updates on the reference GPU completed at30 FPS (mean0.32 ms /maximum0.52 ms per SDK update); physical smoothness requires user observation.
