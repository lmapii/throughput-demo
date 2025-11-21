
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
