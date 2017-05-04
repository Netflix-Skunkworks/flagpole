# flagpole
Flag arg parser to build out a dictionary with optional keys.

[![Version](http://img.shields.io/pypi/v/flagpole.svg?style=flat)](https://pypi.python.org/pypi/flagpole/)

[![Build Status](https://travis-ci.org/monkeysecurity/flagpole.svg?branch=master)](https://travis-ci.org/monkeysecurity/flagpole)

[![Coverage Status](https://coveralls.io/repos/github/monkeysecurity/flagpole/badge.svg?branch=master&1)](https://coveralls.io/github/monkeysecurity/flagpole?branch=master)

# Install:

`pip install flagpole`

# Usage:

Flagpole is used in [cloudaux](https://github.com/Netflix-Skunkworks/cloudaux) to allow users of cloudaux to specify how the library builds out the items.

Flagpole has two classes: `Flags` and `FlagRegistry`.

### Flags
```python
from flagpole import Flags

FLAGS = Flags('BASE', 'LISTENERS', 'RULES')
print(FLAGS)
# OrderedDict([('BASE', 1), ('LISTENERS', 2), ('RULES', 4), ('ALL', 7), ('None', 0), ('NONE', 0)])

print("{0:b}".format(FLAGS.None).zfill(3))
# 000
print("{0:b}".format(FLAGS.ALL).zfill(3))
# 111
print("{0:b}".format(FLAGS.BASE).zfill(3))
# 001
print("{0:b}".format(FLAGS.LISTENERS).zfill(3))
# 010
print("{0:b}".format(FLAGS.RULES).zfill(3))
# 100

# combine multiple flags (100 & 010 = 110):
print("{0:b}".format(FLAGS.RULES | FLAGS.LISTENERS).zfill(3))
# 110
```

`FLAGS.ALL` and `FLAGS.None` are automatically added.  All others must be added in the constructor.

Note: both `NONE` and `None` are provided as we found casing to be a common user error.

### FlagRegistry

The registry has two parts:
- The decorator `@registry.register(...)`
- The build_out method `registry.build_out(...)`

The FlagRegistry is specialized for the cause of building out a datastructure (a python dictionary) with an arbitrary number of optional fields.

#### FlagRegistry decorator:

The decorator is used to wrap methods to indicate which __flag__ will cause the method to be invoked, whether any other flags are a __dependency__, and under what __key__ the return value should be placed.

Supports wrapping methods with multiple return values.  Each return value can have a separate flag and a separate key.

The decorator has the following keyword arguments:
- __flag__: The wrapped method will only be invoked when `build_out` is invoked with a flag which matches the flag provided here.
    - Can be a flag (like `FLAG.RULES`), or for multiple return values, can be a list or tuple.  See the [source](flagpole/__init__.py) for an example.
- __key__: The return value of the wrapped function will be appended to the result dictionary using the key provided. *This keyword argument is optional*.  If not provided, the return value is merged (`dict.update(other_dict)`) with the result dictionary.
    - Can be a string, or for multiple return values, can be a list or tuple.  See the [source](flagpole/__init__.py) for an example.
- __depends_on__: If the wrapped method must not be called until another wrapped method is executed, you must put the __flag__ of the other method here.  *This keyword argument is optional*.  If provided, the results of the function for which this one depends on should be passed in as an argument to this function.

#### FlagRegistry build_out:

The `registry.build_out(...)` method takes the following arguments:

 - __flags__: User-supplied combination of FLAGS.  (ie. `flags = FLAGS.CORS | FLAGS.WEBSITE`)
 - __pass_datastructure__: To pass the result dictionary as an arg to each decorated method, set this to True.  Otherwise it will only be sent if a dependency is detected.
 - __start_with__: You can pass in a dictionary for build_out to mutate. By default, build_out will create a new dictionary and return it.
 - __*args__: Passed on to the method registered in the FlagRegistry
 - __**kwargs__: Passed on to the method registered in the FlagRegistry
 - __return result__: The dictionary created by combining the output of all executed methods.

The `build_out` method executes all registry decorated methods having a flag which matches that passed into `build_out`.
It will follow any dependency chains to execute methods in the correct order.

The `Flags` combined with the ability to recursively follow dependency chains, are in large part the strength of this package.  This package will also detect any circular depdenencies in the decorated methods and will raise an appropriate exception.

#### Full example:

```python
from flagpole import FlagRegistry, Flags
from cloudaux.aws.elbv2 import describe_listeners
from cloudaux.aws.elbv2 import describe_rules

registry = FlagRegistry()
FLAGS = Flags('BASE', 'LISTENERS', 'RULES')

@registry.register(flag=FLAGS.LISTENERS, key='listeners')
def get_listeners(alb, **conn):
    return describe_listeners(load_balancer_arn=alb['Arn'], **conn)

@registry.register(flag=FLAGS.RULES, depends_on=FLAGS.LISTENERS, key='rules')
def get_rules(alb, **conn):
    rules = list()
    for listener in alb['listeners']:
        rules.append(describe_rules(listener_arn=listener['ListenerArn'], **conn))
    return rules

# key is not specified here, so the return value is merged (`dict.update(other_dict)`) with the result dictionary.
@registry.register(flag=FLAGS.BASE)
def get_base(alb, **conn):
    return {
        'region': conn.get('region'),
        '_version': 1
    }
```

And then you can call `registry.build_out()` like so:

```python
def get_elbv2(alb_arn, flags=FLAGS.ALL, **conn):
    alb = dict(Arn=alb_arn)
    registry.build_out(flags, start_with=alb, pass_datastructure=True, **conn)
    return result
```

Note: You can build any arbitrary combination of flags such as: `flags=FLAGS.RULES | FLAGS.LISTENERS`

The result for this example, when called with `FLAGS.ALL` would be a dictionary in the following structure:

```
{
    'Arn': ...,
    'region': ...,
    'listeners': ['ListenerArn': ...],
    'rules': [...],
    '_version': ...,
}
```

The [FlagRegistry class](flagpole/__init__.py) fully documents its use.