"""Watch-only BIP84 mainnet receive-address derivation from an account zpub.

No seed, xprv or private keys are accepted. The caller MUST persist a unique
monotonic index per order with an atomic DB transaction and never recycle it.
This module does not enable checkout or activate subscriptions.
"""
import hashlib
import hmac
import re

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (55066263022277343669578718895168534326250603453777594175500187360389116729240,
     32670510020758816978083085130507043184471273380659243275938904335757337482424)
ZPUB = bytes.fromhex("04b24746")
HARDENED = 0x80000000


def _hash160(data):
    return hashlib.new("ripemd160", hashlib.sha256(data).digest()).digest()


def _decode_zpub(value):
    if not isinstance(value, str) or not value.startswith("zpub") or len(value) > 130:
        raise ValueError("Mainnet BIP84 account zpub required")
    num = 0
    for char in value:
        if char not in ALPHABET:
            raise ValueError("Invalid base58")
        num = num * 58 + ALPHABET.index(char)
    raw = num.to_bytes((num.bit_length() + 7) // 8, "big")
    raw = b"\0" * (len(value) - len(value.lstrip("1"))) + raw
    if len(raw) != 82 or hashlib.sha256(hashlib.sha256(raw[:-4]).digest()).digest()[:4] != raw[-4:]:
        raise ValueError("Invalid extended key checksum")
    data = raw[:-4]
    if data[:4] != ZPUB or data[4] != 3 or data[45] not in (2, 3):
        raise ValueError("Expected mainnet BIP84 account-level public key")
    key = data[45:78]
    point = _decompress(key)
    return data[13:45], point


def _decompress(key):
    x = int.from_bytes(key[1:], "big")
    if x >= P:
        raise ValueError("Invalid public key")
    y = pow((x*x*x + 7) % P, (P+1)//4, P)
    if (y*y - x*x*x - 7) % P:
        raise ValueError("Invalid curve point")
    if y % 2 != key[0] % 2:
        y = P-y
    return x, y


def _compress(point):
    return bytes([2 + point[1] % 2]) + point[0].to_bytes(32, "big")


def _add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == b[0] and (a[1] + b[1]) % P == 0:
        return None
    if a == b:
        slope = (3*a[0]*a[0] * pow(2*a[1], -1, P)) % P
    else:
        slope = ((b[1]-a[1]) * pow((b[0]-a[0]) % P, -1, P)) % P
    x = (slope*slope-a[0]-b[0]) % P
    return x, (slope*(a[0]-x)-a[1]) % P


def _mul(k):
    point = None
    base = G
    while k:
        if k & 1:
            point = _add(point, base)
        base = _add(base, base)
        k >>= 1
    return point


def _child(chain, point, index):
    if type(index) is not int or not 0 <= index < HARDENED:
        raise ValueError("Only nonhardened child indexes supported")
    digest = hmac.new(chain, _compress(point) + index.to_bytes(4, "big"), hashlib.sha512).digest()
    tweak = int.from_bytes(digest[:32], "big")
    if tweak >= N:
        raise ValueError("Invalid BIP32 child; do not reuse index")
    child = _add(point, _mul(tweak))
    if child is None:
        raise ValueError("Invalid BIP32 child; do not reuse index")
    return digest[32:], child


def _convertbits(data):
    acc = bits = 0
    out = []
    for value in data:
        acc = (acc << 8) | value
        bits += 8
        while bits >= 5:
            bits -= 5
            out.append((acc >> bits) & 31)
    if bits:
        out.append((acc << (5-bits)) & 31)
    return out


def _polymod(values):
    chk = 1
    for v in values:
        top = chk >> 25
        chk = ((chk & 0x1ffffff) << 5) ^ v
        for i, gen in enumerate((0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)):
            if (top >> i) & 1:
                chk ^= gen
    return chk


def _bech32(program):
    values = [0] + _convertbits(program)
    expanded = [3, 3, 0, 2, 3]  # 'bc' HRP expansion: b>>5,c>>5,0,b&31,c&31
    checksum_input = expanded + values + [0]*6
    checksum = _polymod(checksum_input) ^ 1
    return "bc1" + "".join(BECH32[v] for v in values + [
        (checksum >> (5*(5-i))) & 31 for i in range(6)])


def receive_address(account_zpub, index):
    """Derive m/84'/0'/account'/0/index (external chain) P2WPKH address."""
    if type(index) is not int or not 0 <= index < HARDENED:
        raise ValueError("Invalid receive index")
    chain, point = _decode_zpub(account_zpub)
    chain, point = _child(chain, point, 0)
    _, point = _child(chain, point, index)
    return _bech32(_hash160(_compress(point)))
