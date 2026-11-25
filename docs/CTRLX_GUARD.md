# GridPass Guard on Bosch Rexroth ctrlX COREvirtual

The open-source Guard reference runs as a separate developer SNAP on the
amd64 core22 base. It is strictly confined, has no network plugs, does not
run a daemon and cannot drive devices. Its only inputs are bundled synthetic
fixtures. This is an engineering evaluation, not a native ctrlX Data Layer
application, production controller, App Store package or site approval.

## Reproduce

Obtain a licensed COREvirtual test instance from Bosch Rexroth and use
its documented developer installation workflow. The proprietary ctrlX OS
image, credentials and existing GridPass bench are deliberately excluded.

On a Linux build host with Python/pip, snapd (snap pack) and squashfs tools:

```sh
python3 -m venv .venv
PYTHON=.venv/bin/python bash deploy/ctrlx/build.sh
```

This installs hash-pinned, architecture-specific wheels into a temporary
build tree and packs the original Apache-2.0 GridPass code plus dependencies
under their own licenses. Review the dependency licenses and update/audit
the lock before distributing a release binary. Rebuilds need not be
byte-identical SNAP images; trace output must be deterministic.

Transfer only the resulting developer SNAP to the **authorized evaluation
controller**. Use the vendor-approved developer workflow; if local unsigned
SNAP installation is allowed by the test controller, run:

```sh
sudo snap install --dangerous ./gridpass-guard_0.1.0_amd64.snap
snap run gridpass-guard.self-test
snap run gridpass-guard > guard-ctrlx-trace.json
```

Do not use devmode or classic confinement or disable platform protections.
If local installation is not permitted, use a vendor-approved signed
package process. Do not modify or stop any existing control service.

On the host, generate the independent reference trace:

```sh
.venv/bin/python -m pip install '.[guard]'
.venv/bin/python -m gridpass_flexibility.guard_demo examples/guard-site.json > guard-host-trace.json
cmp guard-host-trace.json guard-ctrlx-trace.json
sha256sum guard-host-trace.json guard-ctrlx-trace.json
```

Identical trace bytes and passing self-tests demonstrate reproducible execution
of the reference on the virtual controller, not trustworthy plant measurements.
The test keys are public and synthetic. No physical equipment is addressed.
The actual ctrlX Data Layer/Modbus adapter, protected durable replay state,
trusted time, production key provisioning and operator-approved fail-safe
remain separate release gates. Read [Guard demo limitations](GUARD_DEMO.md).

## Verified evaluation — 2026-11-24

- Target: actual Bosch Rexroth ctrlX COREvirtual guest, amd64, Ubuntu Core 22, Python 3.10.12.
- Installed developer SNAP: gridpass-guard 0.1.0 (local revision x1). The manifest declares strict confinement and no plugs or services.
- `snap run gridpass-guard.self-test`: 5/5 test groups passed, including all 15 fixture scenarios; no skips.
- `snap run gridpass-guard`: exact byte equality with the independently generated host reference trace (SHA-256 `f8e60f53132a5bfe302aecb288dd7a03092cbf1199286f3b688aaa44d7b46f14`). See [synthetic trace](evidence/ctrlx-guard-v0.1.json).
- SNAP SHA-256: `17d7ad867087104f37d0c22b8c4654328675ab56ee7ab3712656fb493bd45682`.
- Existing `gridpass-edge.bench-api` service remained active; no changes to that service or physical equipment were made.
- Initial snap installation command timed out while snapd was restarting. The completed local revision, self-test, and replay were subsequently verified using normal snap commands. No platform protections were changed.

The trace is a reproducible synthetic demonstration, not an attested measurement of real grid equipment. The demonstration keys are public by design.
