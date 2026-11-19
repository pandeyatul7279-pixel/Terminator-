.PHONY: test runtime-install runtime-test sources source-verify kit apk apk-java-test apk-auth-test

test:
	python3 -m unittest discover -s tests -v
	python3 tools/upstreams.py list
	@for file in android/*.sh; do bash -n "$$file" || exit; done
	@for file in android/*.mjs tools/*.mjs; do node --check "$$file" || exit; done

runtime-install:
	node -e 'if (process.versions.node !== "24.22.1" || process.platform !== "linux") throw Error("Use Linux and pinned Node 24.22.1; phone users must use the Ubuntu/Termux installer")'
	npm ci --prefix android/runtime --no-audit --no-fund

runtime-test:
	node android/runtime-smoke.mjs --runtime android/runtime
	node tools/runtime-integration.mjs android/runtime

sources:
	python3 tools/upstreams.py fetch

source-verify:
	python3 tools/upstreams.py verify

kit:
	python3 tools/package_kit.py

apk:
	python3 tools/build_apk.py --prepare --build

apk-java-test:
	python3 tools/test_apk_java.py -v

apk-auth-test:
	node tools/apk-auth-integration.mjs android/runtime
