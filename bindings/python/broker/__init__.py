from . import _broker
from . import utils

import datetime
import ipaddress

#
# Version & Contants
#

VERSION_MAJOR = _broker.Version.MAJOR
VERSION_MINOR = _broker.Version.MINOR
VERSION_PATCH = _broker.Version.PATCH
VERSION_PROTOCOL = _broker.Version.PROTOCOL

VERSION = '%u.%u.%u' % (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)

def compatible(protocol_version):
  """Checks whether another Broker protocol is compatible with this instance."""
  _broker.Version.compatible(protocol_version)

# api_flags
Blocking = _broker.ApiFlags.Blocking
Nonblocking = _broker.ApiFlags.Nonblocking

# frontend
Master = _broker.Frontend.Master
Clone = _broker.Frontend.Clone

# backend
Memory = _broker.Backend.Memory
SQLite = _broker.Backend.SQLite
RocksDB = _broker.Backend.RocksDB

# Broker will only raise exceptions of type BrokerError
class BrokerError(Exception):
  """A Broker-specific error."""

  def __init__(self, *args, **kwargs):
    Exception.__init__(self, *args, **kwargs)


EC = _broker.EC
Error = _broker.Error
PeerStatus = _broker.PeerStatus
PeerFlags = _broker.PeerFlags
EndpointInfo = _broker.EndpointInfo
Message = _broker.Message
NetworkInfo = _broker.NetworkInfo
PeerInfo = _broker.PeerInfo
Status = _broker.Status

#
# Data Model
#

Count = _broker.Count
Timespan = _broker.Timespan
Timestamp = _broker.Timestamp
Port = _broker.Port

def now():
  return _broker.now()

class Data:
  def __init__(self, x = None):
    if x is None:
      self.data = _broker.Data()
    elif isinstance(x, (bool, int, float, str, Count, Timespan, Timestamp,
                        Port)):
      self.data = _broker.Data(x)
    elif isinstance(x, datetime.timedelta):
      us = x.microseconds + (x.seconds + x.days * 24 * 3600) * 10**6
      ns = us * 10**3
      self.data = _broker.Timespan(ns)
    elif isinstance(x, datetime.datetime):
      #self.data = _broker.Timestamp(x.timestamp()) # Python 3 only
      time_since_epoch = (x - datetime.datetime(1970, 1, 1)).total_seconds()
      self.data = _broker.Timestamp(time_since_epoch)
    elif isinstance(x, ipaddress.IPv4Address):
      self.data = _broker.Data(_broker.Address(x.packed, 4))
    elif isinstance(x, ipaddress.IPv6Address):
      self.data = _broker.Data(_broker.Address(x.packed, 6))
    elif isinstance(x, ipaddress.IPv4Network):
      address = _broker.Address(x.network_address.packed, 4)
      length = x.prefixlen
      self.data = _broker.Data(_broker.Subnet(address, length))
    elif isinstance(x, ipaddress.IPv6Network):
      address = _broker.Address(x.network_address.packed, 6)
      length = x.prefixlen
      self.data = _broker.Data(_broker.Subnet(address, length))
    elif isinstance(x, list):
      v = _broker.Vector(list(map(lambda d: Data(d).get(), x)))
      self.data = _broker.Data(v)
    elif isinstance(x, set):
      s = _broker.Set(list(map(lambda d: Data(d).get(), x)))
      self.data = _broker.Data(s)
    elif isinstance(x, dict):
      t = _broker.Table({Data(k).get(): Data(v).get() for k, v in x.items()})
      self.data = _broker.Data(t)
    else:
      raise BrokerError("unsupported data type: " + str(type(x)))

  def get(self):
    return self.data

  def __eq__(self, other):
    if isinstance(other, Data):
      return self.data == other.data
    elif isinstance(other, _broker.Data):
      return self.data == other
    else:
      return self == Data(other)

  def __ne__(self, other):
    return not self.__eq__(other)

  def __str__(self):
    return str(self.data)


# TODO: complete interface
class Store:
  def __init__(self, handle):
    self.store = handle

  def name(self):
    return self.store.name()


class Endpoint:
   def __init__(self, handle):
     self.endpoint = handle

   def listen(self, address = "", port = 0):
     return self.endpoint.listen(address, port)

   def peer(self, other):
     self.endpoint.peer(other)

   def peer(self, address, port):
     self.endpoint.peer(str(address), port)

   def unpeer(self, other):
     self.endpoint.unpeer(other)

   def unpeer(self, address, port):
     self.endpoint.unpeer(str(address), port)

   def publish(self, topic, data):
     x = data if isinstance(data, Data) else Data(data)
     self.endpoint.publish(topic, x.get())

   def attach(self, frontend, name, backend = None, backend_options = None):
     if frontend == Frontend.Clone:
       return self.endpoint.attach_clone(name)
     else:
       return self.endpoint.attach_master(name, backend, backend_options)

class Mailbox:
  def __init__(self, handle):
    self.mailbox = handle

  def descriptor(self):
    return self.mailbox.descriptor()

  def empty(self):
    return self.mailbox.empty()

  def count(self, n = -1):
    return self.mailbox.count(n)


class Message:
  def __init__(self, handle):
    self.message = handle

  def topic(self):
    return self.message.topic().string()

  def data(self):
    return self.message.data() # TODO: unwrap properly

  def __str__(self):
    return "%s -> %s" % (self.topic(), str(self.data()))


class BlockingEndpoint(Endpoint):
  def __init__(self, handle):
    super(BlockingEndpoint, self).__init__(handle)

  def subscribe(self, topic):
    self.endpoint.subscribe(topic)

  def unsubscribe(self, topic):
    self.endpoint.unsubscribe(topic)

  def receive(self, fun1 = None, fun2 = None):
    if fun1 is None:
      return Message(self.endpoint.receive())
    if fun2 is None:
      if utils.arity(fun1) == 1:
        return self.endpoint.receive_status(fun1)
      if utils.arity(fun1) == 2:
        return self.endpoint.receive_msg(fun1)
      raise BrokerError("invalid receive callback arity; must be 1 or 2")
    return self.endpoint.receive_msg_or_status(fun1, fun2)

  def mailbox(self):
    return Mailbox(self.endpoint.mailbox())


class NonblockingEndpoint(Endpoint):
  def __init__(self, handle):
    super(NonblockingEndpoint, self).__init__(handle)

  def subscribe(self, topic, fun):
    self.endpoint.subscribe_msg(topic, fun)

  def on_status(fun):
    self.endpoint.subscribe_status(fun)

  def unsubscribe(self, topic):
    self.endpoint.unsubscribe(topic)


class Context:
  def __init__(self):
    self.context = _broker.Context()

  def spawn(self, api):
    if api == Blocking:
      return BlockingEndpoint(self.context.spawn_blocking())
    elif api == Nonblocking:
      return NonblockingEndpoint(self.context.spawn_nonblocking())
    else:
      raise BrokerError("invalid API flag: " + str(api))
