# flagpole
Flag arg parser to build out a dictionary with optional keys.

[![Version](http://img.shields.io/pypi/v/flagpole.svg?style=flat)](https://pypi.python.org/pypi/flagpole/)

[![Build Status](https://travis-ci.org/monkeysecurity/flagpole.svg?branch=master)](https://travis-ci.org/monkeysecurity/flagpole)

[![Coverage Status](https://coveralls.io/repos/github/monkeysecurity/flagpole/badge.svg?branch=master&1)](https://coveralls.io/github/monkeysecurity/flagpole?branch=master)

# Install:

`pip install flagpole`

# Usage:

Flagpole is used in [cloudaux](https://github.com/Netflix-Skunkworks/cloudaux) to allow users of cloudaux to specify how the library builds out the items.

```python
from flagpole import FlagRegistry, Flags

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

```
def get_elbv2(alb_arn, flags=FLAGS.ALL, **conn):
    result = dict(Arn=alb_arn)
    registry.build_out(result, flags, result, **conn)
    return result
```

Note that `build_out` does not have a return value. It mutates the `result` dictionary passed in.

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

