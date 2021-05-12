import pytest
import testinfra

# @jpevrard: This test should be run with the base container - how do I tell pytest about this?


NONFIPS_DIGESTS = (
	"blake2b512",
	"blake2s256",
	"gost",
	"md4",
	"md5",
	"mdc2",
	"rmd160",
	"sm3",
)
FIPS_DIGESTS = (
	"sha1",
	"sha224",
	"sha256",
	"sha3-224",
	"sha3-256",
	"sha3-384",
	"sha3-512",
	"sha384",
	"sha512",
	"sha512-224",
	"sha512-256",
	"shake128",
	"shake256",
)
ALL_DIGESTS = NONFIPS_DIGESTS + FIPS_DIGESTS


def host_fips_supported():
    import os.path

    return os.path.exists("/proc/sys/crypto/fips_enabled")

def host_fips_enabled():
    if not host_fips_supported():
    	return False

    with open("/proc/sys/crypto/fips_enabled") as f:
    	return f.read().strip() == "1"

with_fips = pytest.mark.skipif(not host_fips_enabled(), reason = "host not running in FIPS 140 mode")
without_fips = pytest.mark.skipif(host_fips_enabled(), reason = "host running in FIPS 140 mode")

@with_fips
def test_openssl_fips_hashes(container):
    for md in NONFIPS_DIGESTS:
    	cmd = container.connection.run(f"openssl {md} /dev/null")

	assert cmd.rc != 0 && "not a known digest" in rc.stdout

    for md in FIPS_DIGESTS:
    	assert container.connection.run(f"openssl {md} /dev/null").rc == 0

@without_fips
def test_openssl_hashes(container):
    for md in ALL_DIGESTS:
    	assert container.connection.run(f"openssl {md} /dev/null").rc == 0
