# Usage

```bash
$ mkdir .venv
$ pipenv install --dev
$ source .venv/bin/activate

$ rm -rf build deps
$ west init --local --manifest-file west-sdk-nrf.yml demo
$ west update --narrow -o=--depth=1 && west zephyr-export
$ pip install -r deps/zephyr/scripts/requirements.txt
$ pip install --upgrade pip

# building, e.g., without sysbuild
$ west build --no-sysbuild --board nrf52840dk/nrf52840 demo

# debugging
$ west debugserver --skip-rebuild

# flashing to target
$ west flash --skip-rebuild
```


# Building for RTT

```bash
# building, e.g., without sysbuild
$ west build --no-sysbuild --board nrf52840dk/nrf52840 demo -- -DEXTRA_CONF_FILE="prj-rtt.conf"
```

Needs `JLinkRTTViewer` since the RTT shell doesn't seem to work reliably via any other method (e.g., `OpenOCD`) but that still needs to be verified.

Also, on targets without a built-in J-Link debugger this won't work at all.


# Shell demo

Given that we use the following codes, see the [board's overlay](./boards/nrf52840dk_nrf52840.overlay):

```py
# zephyr/dt-bindings/input/input-event-codes.h
# type for INPUT_EV_KEY == 1 (but the type is ignored in our callback)
INPUT_KEY_0 = 11
INPUT_KEY_1 = 2
```

We can already simulate input events using the subsystem's shell:

```bash
# input report <type> <code> <value>
# both, INPUT_KEY_0 and INPUT_KEY_1 allow us to toggle the LED
uart:~$ input report 1 11 1
uart:~$ input report 1 2 1

# zero-values do not affect the LED
uart:~$ input report 1 11 1
uart:~$ input report 1 2 0

# and any other event codes neither
uart:~$ input report 1 12 1
```

Alternatively, we can use the shell commands implemented in [`main.c`](./src/main.c):

```bash
# any value > 1 is interpreted as a button push
uart:~$ demo simulate_button 1
# a value == 0 is ignored
uart:~$ demo simulate_button 0
```

These don't go through the `input` subsystem but are processed directly.
