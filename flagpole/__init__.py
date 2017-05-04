from collections import defaultdict


class FlagRegistry:
    
    def __init__(self):
        self.r = defaultdict(list)

    def register(self, flag, depends_on=0, key=None):
        """
        optional methods must register their flag with the FlagRegistry.

        The registry:
            - stores the flags relevant to each method.
            - methods may be a dependent of other methods.
            - stores the dictionary key the return value will be saved as.
            - for methods with multiple return values, stores the flag/key for each return value.

        Single Return Value Example:
        ----------------------------

        @FlagRegistry.register(flag=FLAGS.LIFECYCLE, key='lifecycle_rules')
        def get_lifecycle(bucket_name, **conn):
            pass

        In this example, the `get_lifecycle` method will be called when the `LIFECYCLE` flag is set.
        The return value will be appended to the results dictionary with the 'lifecycle_rules' key.

        Multiple Return Value Example:
        ------------------------------

        @FlagRegistry.register(
            flag=(FLAGS.GRANTS, FLAGS.GRANT_REFERENCES, FLAGS.OWNER),
            key=('grants', 'grant_references', 'owner'))
        def get_grants(bucket_name, include_owner=True, **conn):
            pass

        In this example, the `get_grants` method will be called when the `GRANTS`, `GRANT_REFERENCES`, or `OWNER` flags are set.
        The return values will be appended to the results dictionary with the corresponding 'grants', 'grant_references', 'owner' key.

        Dependency Example:
        -------------------

        @ALBFlagRegistry.register(flag=FLAGS.LISTENERS, key='listeners')
        def get_listeners(alb, **conn):
            return describe_listeners(load_balancer_arn=alb['Arn'], **conn)


        @ALBFlagRegistry.register(flag=FLAGS.RULES, depends_on=FLAGS.LISTENERS, key='rules')
        def get_rules(alb, **conn):
            rules = list()
            for listener in alb['listeners']:
                rules.append(describe_rules(listener_arn=listener['ListenerArn'], **conn))
            return rules

        In this example, `get_rules` requires the listener ARNs which are obtained by calling `get_listeners`.  So, `get_rules`
        depends on `get_listeners`.  The `alb` object passed into `get_rules` will have already been mutated by `get_listeners`
        so it can iterate over the values in alb['listeners'] to extract the information it needs.

        The `get_rules` method does not itself mutate the alb object, but it instead returns a new object (`rules`) which is
        appended to the final return value by the FlagRegistry.
        """
        def decorator(fn):
            flag_list = flag
            key_list = key
            if type(flag) not in [list, tuple]:
                flag_list = [flag] 
            if type(key) not in [list, tuple]: 
                key_list = [key]
            for idx in range(len(flag_list)):
                self.r[fn].append(
                    dict(flag=flag_list[idx],
                         depends_on=depends_on,
                         key=key_list[idx],
                         rtv_ix=idx))
            return fn
        return decorator

    def _validate_flags(self, flags):
        """
        Iterate over the methods to make sure we set the flag for any
        dependencies if the dependent is set.

        Example: ALB.RULES depends on ALB.LISTENERS, but flags does not have ALB.LISTENERS set.
        We will modify flags to make sure ALB.LISTENERS is set.

        :param flags:  The flags passed into `build_out()`.
        :return flags: Same as the argument by the same name, but potentially modified
        to have any dependencies.
        """
        for method in self.r:
            method_flag, method_dependencies = self._get_method_flag(method)

            if not flags & method_flag:
                continue

            flags = flags | self._calculate_dependency_flag(method)

        return flags

    def _calculate_dependency_flag(self, method, calculated=None):
        """
        Given a method that may or may not contain dependencies, create a binary flag
        which represents all dependent methods.
        
        As dependencies may be multiple levels deep, we use a recursive approach.
        
        Note: Will raise an Exception if a dependency cycle is detected.
        
        :param method: Starting point for calculating dependency flag
        :param calculated: set of methods this function has been called with.  Used to detect dependency cycles.
        :return dependencies: binary flag (int) created by binary-ORing each dependency in the chain.
        """
        if not calculated:
            calculated = set([method])
        else:
            calculated.add(method)
        
        method_flag, dependencies = self._get_method_flag(method)
        methods = self._find_methods_matching_flag(dependencies)
        for m in methods:
            if m in calculated:
                raise Exception('Circular Dependency Error.')
            dependencies = dependencies | self._calculate_dependency_flag(m, calculated=calculated)
        return dependencies

    def _find_methods_matching_flag(self, flag):
        """
        Given a flag, iterates over the method registry and returns a list of 
        all methods which match the flag.
        
        :param flag: flag to match against
        :return results: list of matching methods.
        """
        results = list()
        for m in self.r:
            method_flag, dependencies = self._get_method_flag(m)
            if method_flag & flag:
                results.append(m)
        return results 

    def _get_method_flag(self, method):
        """
        Helper method to return the method flag and the flag of any dependencies.

        As a method may have multiple return values, each with their own flags, the method
        flag will be the combination (logical OR) of each.

        :param method: Must be a @FlagRegistry.register() decorated method.
        :return method_flag: Combination of all flags associated with this method.
        :return method_dependencies: Combination of all dependencies associated with this method.
        """
        method_flag = 0
        method_dependencies = 0

        for entry in self.r[method]:
            method_flag = method_flag | entry['flag']
            method_dependencies = method_dependencies | entry['depends_on']
        return method_flag, method_dependencies

    def _execute_method(self, method, method_flag, method_dependencies, executed_flag, result, pass_datastructure, flags, *args, **kwargs):
        """
        Executes a @FlagRegistry.register() decorated method.

        First checks the flags to see if the method is required.
        Next, checks if there are any dependent methods that have yet to be executed.
            If so, return False instead of executing.  We will try again on a later pass.
        Finally, execute the method and mutate the result dictionary to contain the results
        from each return value.

        :return True: If this method was either executed or should be removed from future passes.
        :return False: If this method could not be executed because of outstanding dependent methods. (Try again later)
        """
        if not flags & method_flag:
            # by returning True, we remove this method from the method_queue.
            return True

        # Check if all method dependencies have been executed.
        # If a method still has unexecuted dependencies, add the method to the queue.
        if method_dependencies and not (method_dependencies & executed_flag):
            return False

        # At least one of the return values is required. Call the method.
        if (result not in args) and (method_dependencies or pass_datastructure):
            # Need to pass along dict(result) if it's not already in *args
            retval = method(dict(result), *args, **kwargs)
        else:
            retval = method(*args, **kwargs)

        for entry in self.r[method]:
            if len(self.r[method]) > 1:
                key_retval = retval[entry['rtv_ix']]
            else:
                key_retval = retval
            if flags & entry['flag']:
                if entry['key']:
                    result.update({entry['key']: key_retval})
                else:
                    result.update(key_retval)
        return True

    def _do_method_pass(self, method_queue, executed_flag, result, pass_datastructure, flags, *args, **kwargs):
        """
        Loop over available methods, executing those that are ready.
        - Raise an exception if we don't execute any methods on a given path. (circular dependency)

        :return next_method_queue: The list of methods to use for the next pass.
        :return executed_flag: Binary combination of all flags whose attached methods have been executed.
        """
        did_execute_method = False
        next_method_queue = list()

        for method in method_queue:
            method_flag, method_dependencies = self._get_method_flag(method)
            if self._execute_method(method, method_flag, method_dependencies, executed_flag, result, pass_datastructure, flags, *args, **kwargs):
                did_execute_method = True
                executed_flag = int(executed_flag | method_flag)
            else:
                next_method_queue.append(method)

        if not did_execute_method:
            raise Exception('Circular Dependency Error.')

        return next_method_queue, executed_flag

    def build_out(self, flags, *args, **kwargs):
        """
        Provided user-supplied flags, `build_out` will find the appropriate methods from the FlagRegistry
        and mutate the `result` dictionary.

        Stage 1: Set the flags for any dependencies if not already set.
        Stage 2: Repeatedly loop over available methods, executing those that are ready.
        - Break when we've executed all methods.
        - Break and error out if we don't execute any on a given pass.

        :param flags: User-supplied combination of FLAGS.  (ie. `flags = FLAGS.CORS | FLAGS.WEBSITE`)
        :param pass_datastructure: To pass the result dictionary as an arg to each decorated method, set this to True.  Otherwise it will only be sent if a dependency is detected.
        :param start_with: You can pass in a dictionary for build_out to mutate. By default, build_out will create a new dictionary and return it.
        :param *args: Passed on to the method registered in the FlagRegistry
        :param **kwargs: Passed on to the method registered in the FlagRegistry
        :return result: The dictionary created by combining the output of all executed methods.
        """
        pass_datastructure = kwargs.pop('pass_datastructure', False)
        start_with = kwargs.pop('start_with', dict())

        flags = self._validate_flags(flags)
        result = start_with or dict()

        method_queue = self.r.keys()
        executed_flag = 0
        while len(method_queue) > 0:
            method_queue, executed_flag = self._do_method_pass(
                method_queue, executed_flag, result, pass_datastructure, flags,
                *args, **kwargs)
        return result


class Flags(object):
    def __init__(self, *flags):
        from collections import OrderedDict
        self.flags = OrderedDict()
        self._idx = 0
        for flag in flags:
            self.flags[flag] = 2**self._idx
            self._idx += 1
        self.flags['ALL'] = 2**self._idx-1
        self.flags['None'] = 0
        self.flags['NONE'] = 0

    def __getattr__(self, k):
        return self.flags[k]

    def __repr__(self):
        return str(self.flags)