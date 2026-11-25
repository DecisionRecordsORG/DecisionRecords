"""
The address of the visitor who made the current request.

One function, ``get_client_address()``, answers "who is this request from" for
everything that needs it: the rate limiter's bucket, login history, the audit
log and security log lines. They must not disagree, and none of them may take
the answer from a header the visitor can write.

How the address is found
------------------------
The only address the application knows for certain is the peer of the TCP
connection (``request.remote_addr``). Behind a reverse proxy that peer is the
proxy, for every visitor alike. A proxy passes the visitor's address on in
``X-Forwarded-For``, appending the address that connected to it, so with two
proxies the header reads ``<whatever the visitor sent>, <visitor>, <outer proxy>``.

Anybody can send an ``X-Forwarded-For`` header, so the header is read only
when the peer is a proxy the operator has named in ``TRUSTED_PROXIES``, and it
is read from the right: entries written by trusted proxies are skipped, and
the first address that is not a trusted proxy is the visitor. Everything to
the left of it was supplied by the visitor and is ignored.

``TRUSTED_PROXIES`` is a comma-separated list of addresses and networks
(``172.17.0.1, 10.0.0.0/8, 2001:db8::/32``). It is empty by default: no header
is trusted and the address is the connection's peer. That is always safe, and
it is right when visitors connect to the application directly. Behind a proxy
it means all visitors look like one (they share one rate-limit bucket and the
audit log records the proxy), so an installation behind a proxy should set it.
See docs/configuration.md.

Code that knows of more proxies (the Enterprise Edition knows the published
address ranges of its content delivery network) adds them with
``trust_proxy_networks()``. The public code names no provider.
"""

import ipaddress
import logging
import os

from flask import has_request_context, request

logger = logging.getLogger(__name__)

ENV_VAR = 'TRUSTED_PROXIES'
FORWARDED_HEADER = 'X-Forwarded-For'

# Entries of X-Forwarded-For that are looked at. A real chain is two or three
# long; the cap keeps a hostile header from costing anything.
MAX_FORWARDED_HOPS = 20

# Networks named by the operator (TRUSTED_PROXIES) and networks added by code.
_env_networks = ()
_extra_networks = ()


def _parse_networks(entries, source):
    """Parse addresses and CIDR networks; an entry that is neither is skipped."""
    networks = []
    for entry in entries:
        text = str(entry).strip()
        if not text:
            continue
        try:
            networks.append(ipaddress.ip_network(text, strict=False))
        except ValueError:
            # Trusting less is the safe direction, so a bad entry is dropped
            # and said out loud instead of stopping the application.
            logger.error("%s: %r is not an IP address or network; ignored", source, text)
    return tuple(networks)


def load_trusted_proxies(value=None):
    """Read TRUSTED_PROXIES (or `value`) and replace the operator's list.

    Called once when this module is imported. Tests call it again after
    changing the environment.
    """
    global _env_networks
    if value is None:
        value = os.environ.get(ENV_VAR, '')
    _env_networks = _parse_networks(value.split(','), ENV_VAR)
    return _env_networks


def trust_proxy_networks(networks, source='trust_proxy_networks'):
    """Add proxy networks to the trusted set, on top of TRUSTED_PROXIES.

    For code that knows the addresses of a proxy in front of the installation.
    Adding the same network twice has no effect.
    """
    global _extra_networks
    known = set(_extra_networks)
    added = [n for n in _parse_networks(networks, source) if n not in known]
    _extra_networks = _extra_networks + tuple(dict.fromkeys(added))


def reset_extra_proxy_networks():
    """Forget networks added with trust_proxy_networks(). For tests."""
    global _extra_networks
    _extra_networks = ()


def trusted_proxy_networks():
    """Every network currently trusted to report a visitor's address."""
    return _env_networks + _extra_networks


def _parse_address(text):
    """An ip_address for `text`, or None. IPv4-mapped IPv6 becomes IPv4."""
    if not text:
        return None
    text = text.strip()
    # A zone id (fe80::1%eth0) is local to a host and never part of a network.
    text = text.split('%', 1)[0]
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    if address.version == 6 and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def is_trusted_proxy(address):
    """Whether `address` (text or ip_address) is in the trusted set."""
    if isinstance(address, str):
        address = _parse_address(address)
    if address is None:
        return False
    return any(address.version == network.version and address in network
               for network in trusted_proxy_networks())


def _forwarded_hops(req):
    """The entries of X-Forwarded-For, nearest proxy last."""
    values = req.headers.getlist(FORWARDED_HEADER)
    if not values:
        return []
    hops = [hop.strip() for hop in ','.join(values).split(',')]
    return hops[-MAX_FORWARDED_HOPS:]


def get_client_address(req=None):
    """The visitor's address for the current request, as text.

    The connection's peer, unless the peer is a trusted proxy: then the
    nearest address in X-Forwarded-For that is not itself a trusted proxy.
    Returns None outside a request.
    """
    if req is None:
        if not has_request_context():
            return None
        req = request

    peer_text = req.remote_addr
    peer = _parse_address(peer_text)
    if peer is None:
        # A unix socket or something else without an address: nothing to
        # check a header against, so nothing is believed.
        return peer_text
    if not is_trusted_proxy(peer):
        return str(peer)

    client = peer
    for hop in reversed(_forwarded_hops(req)):
        address = _parse_address(hop)
        if address is None:
            # Not an address. A trusted proxy does not write one, so the
            # chain ends at the last address that could be believed.
            break
        client = address
        if not is_trusted_proxy(address):
            break
    return str(client)


def rate_limit_key():
    """The rate limiter's bucket for the current request.

    The visitor's address. An IPv6 visitor is counted by /64, the smallest
    block a network hands to one subscriber, since one device can use any
    address in its /64 and would otherwise have as many buckets as it likes.
    """
    text = get_client_address()
    address = _parse_address(text)
    if address is None:
        return text or 'unknown'
    if address.version == 6:
        return str(ipaddress.ip_network((int(address) >> 64 << 64, 64)))
    return str(address)


load_trusted_proxies()
