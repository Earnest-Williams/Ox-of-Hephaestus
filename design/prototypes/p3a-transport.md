# P3a external Evennia transport

This uses Evennia's **ordinary** v1 WebSocket client protocol at
ws://127.0.0.1:4002, not an internal game API or an in-process command
dispatcher. Each AI character requires an account with a dedicated password,
a valid playable-character assignment and a character puppet lock. The
handler uses normal connect / ic / oxidentity commands and refuses to act
until the server returns its nonce paired with the expected character dbref.

This is a real live external client, **not yet a full WorldPort**:
arbitrary command text is not a transaction receipt. P3b will introduce
world-owned action IDs and durable reconciliation before enabling physical
GOAP actions through the socket. Unencrypted ws:// is limited to loopback.
Off-machine use requires wss://.

For a credential-free CI demonstration, the Ox P3 external crew transport
workflow creates disposable bot accounts, starts the actual Evennia portal,
executes ox_ai.scenarios.p3a_probe from a separate process, and proves an
unrelated valid bot account cannot puppet Ari.

Do not enable registration, expose the development server publicly, or
place bot passwords in logs or source control.
