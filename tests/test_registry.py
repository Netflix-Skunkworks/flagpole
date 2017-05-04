import unittest
from flagpole import Flags, FlagRegistry


class TestRegistry(unittest.TestCase):

    def test_register_single_return_value(self):

        FLAGS = Flags('ONE', 'TWO')
        registry = FlagRegistry()

        @registry.register(flag=FLAGS.ONE) 
        def some_method():
            pass

        self.assertEqual(len(registry.r.keys()), 1)

        @registry.register(flag=FLAGS.TWO) 
        def some_other_method():
            pass

        self.assertEqual(len(registry.r.keys()), 2)

    def test_register_multiple_return_value(self):
        FLAGS = Flags('PETS', 'FARM_ANIMALS', 'WILD_ANIMALS')
        registry = FlagRegistry()

        @registry.register(
            flag=(FLAGS.PETS, FLAGS.FARM_ANIMALS, FLAGS.WILD_ANIMALS),
            key=('pets', 'farm', 'wild')) 
        def some_method():
            return 'cat', 'pig', 'rhino'

        self.assertEqual(len(registry.r.keys()), 1)

        entries = registry.r[some_method]
        self.assertEqual(len(entries), 3)
        
        pet_entry = entries[0]
        farm_entry = entries[1]
        wild_entry = entries[2]
        
        self.assertEqual(pet_entry['flag'], FLAGS.PETS)
        self.assertEqual(farm_entry['flag'], FLAGS.FARM_ANIMALS)
        self.assertEqual(wild_entry['flag'], FLAGS.WILD_ANIMALS)

        self.assertEqual(pet_entry['key'], 'pets')
        self.assertEqual(farm_entry['key'], 'farm')
        self.assertEqual(wild_entry['key'], 'wild')

        self.assertEqual(pet_entry['rtv_ix'], 0)
        self.assertEqual(farm_entry['rtv_ix'], 1)
        self.assertEqual(wild_entry['rtv_ix'], 2)
        
        for entry in entries:
            self.assertEqual(entry['depends_on'], 0) 
        
    def test_validate_flags(self):
        FLAGS = Flags('ONE', 'TWO', 'THREE', 'FOUR')
        registry = FlagRegistry()
       
        @registry.register(flag=FLAGS.ONE, key='one') 
        def method_one():
            pass
        
        @registry.register(flag=FLAGS.TWO, depends_on=FLAGS.ONE, key='two')
        def method_two():
            pass
        
        @registry.register(flag=FLAGS.THREE, key='three') 
        def method_three():
            pass
        
        @registry.register(flag=FLAGS.FOUR, depends_on=FLAGS.TWO, key='four') 
        def method_four():
            pass
        
        self.assertEqual(
            registry._calculate_dependency_flag(method_four),
            FLAGS.ONE | FLAGS.TWO)
        
        self.assertEqual(
            set(registry._find_methods_matching_flag(FLAGS.ONE | FLAGS.THREE)),
            set([method_one, method_three]))

        self.assertEqual(
            set(registry._find_methods_matching_flag(FLAGS.FOUR)),
            set([method_four]))
       
        # Asking for FOUR, which depends on TWO, which depends on ONE
        flag = FLAGS.FOUR
        self.assertEqual(
            registry._validate_flags(flag),
            FLAGS.ONE | FLAGS.TWO | FLAGS.FOUR)
       
        flag = FLAGS.THREE
        self.assertEqual(
            registry._validate_flags(flag),
            FLAGS.THREE)

        flag = FLAGS.TWO
        self.assertEqual(
            registry._validate_flags(flag),
            FLAGS.ONE | FLAGS.TWO)
    
    def test_get_method_flag(self):
        FLAGS = Flags('PETS', 'FARM_ANIMALS', 'WILD_ANIMALS', 'OTHER')
        registry = FlagRegistry()

        @registry.register(
            flag=(FLAGS.PETS, FLAGS.FARM_ANIMALS, FLAGS.WILD_ANIMALS),
            key=('pets', 'farm', 'wild')) 
        def some_method():
            return 'cat', 'pig', 'rhino'

        @registry.register(flag=FLAGS.OTHER, depends_on=FLAGS.PETS, key='other') 
        def method_other():
            pass
        
        method_flag, method_dependencies = registry._get_method_flag(some_method)
        
        self.assertEqual(method_flag, FLAGS.PETS | FLAGS.FARM_ANIMALS | FLAGS.WILD_ANIMALS)
        self.assertEqual(method_dependencies, 0)

        method_flag, method_dependencies = registry._get_method_flag(method_other)
        
        self.assertEqual(method_flag, FLAGS.OTHER)
        self.assertEqual(method_dependencies, FLAGS.PETS)
    
    def test_circular(self):
        FLAGS = Flags('ONE', 'TWO')
        registry = FlagRegistry()

        @registry.register(flag=FLAGS.ONE, depends_on=FLAGS.TWO, key='one')
        def method_one():
            pass

        @registry.register(flag=FLAGS.TWO, depends_on=FLAGS.ONE, key='two')
        def method_two():
            pass

        with self.assertRaises(Exception) as context:
            registry._do_method_pass([method_one, method_two], 0, dict(), False, flags=FLAGS.ONE | FLAGS.TWO)
            self.assertTrue('Circular Dependency Error' in str(context.exception))
        
        with self.assertRaises(Exception) as context:
            registry._calculate_dependency_flag(method_two)
            self.assertTrue('Circular Dependency Error' in str(context.exception))
        
        
    def test_do_method_pass_requires_another_pass(self):
        FLAGS = Flags('ONE', 'TWO')
        registry = FlagRegistry()

        @registry.register(flag=FLAGS.ONE, key='one')
        def method_one():
            return 1

        @registry.register(flag=FLAGS.TWO, depends_on=FLAGS.ONE, key='two')
        def method_two(data):
            # Note: Any method that sets depends_on must take an argument holding the datastructure being built out
            return 2

        result = dict()
        next_method_queue, executed_flag = registry._do_method_pass(
            [method_two, method_one], 0, result, False, flags=FLAGS.ONE | FLAGS.TWO)

        self.assertEqual(len(next_method_queue), 1) 
        self.assertEqual(executed_flag, FLAGS.ONE)
        self.assertEqual(set(result.keys()), set(['one']))

        next_method_queue, executed_flag = registry._do_method_pass(
            next_method_queue, executed_flag, result, False, flags=FLAGS.ONE | FLAGS.TWO)

        self.assertEqual(len(next_method_queue), 0) 
        self.assertEqual(executed_flag, FLAGS.ONE | FLAGS.TWO)
        self.assertEqual(set(result.keys()), set(['one', 'two']))

    def test_build_out(self):
        FLAGS = Flags('PEOPLE', 'HOBBIES')
        registry = FlagRegistry()

        @registry.register(flag=FLAGS.PEOPLE, key='people') 
        def method_people(*args):
            return dict(simon='123', george='234')

        @registry.register(flag=FLAGS.HOBBIES, depends_on=FLAGS.PEOPLE, key='hobbies') 
        def method_hobbies(result):
            hobbies = {
                '123': ['mountain biking', 'skiing'],
                '234': ['snail collecting', 'roaring like a dinosaur']}

            return_value = dict()
            for person, uid in result['people'].items():
                return_value[person] = hobbies.get(uid)

            return return_value

        # Simple example
        #   - No dependencies
        #   - Single Flag
        #   - No starts_with dict
        #   - Default pass_dictionary value (False)

        result = registry.build_out(FLAGS.PEOPLE)
        self.assertEqual(result, dict(people=dict(simon='123', george='234')))

        # Only send the leaf node of a dependency chain. Rely on registry to calculate dependencies.
        # Relies on the registry to detect that hobbies has a dependency and will automatically
        #   pass the datastructure (result) to it as an arg.

        result = registry.build_out(FLAGS.HOBBIES)
        self.assertEqual(result, dict(
            people=dict(simon='123', george='234'),
            hobbies=dict(simon=['mountain biking', 'skiing'], george=['snail collecting', 'roaring like a dinosaur'])))

        # Explicitly send all required methods in the dependency chain.
        # Relies on the registry to detect that hobbies has a dependency and will automatically
        #   pass the datastructure (result) to it as an arg.

        result_1 = registry.build_out(FLAGS.PEOPLE | FLAGS.HOBBIES)
        self.assertEqual(result, result_1)

        FLAGS = Flags('PETS', 'FARM_ANIMALS', 'WILD_ANIMALS')
        registry = FlagRegistry()

        @registry.register(
            flag=(FLAGS.PETS, FLAGS.FARM_ANIMALS, FLAGS.WILD_ANIMALS),
            key=('pets', 'farm', 'wild')) 
        def some_method():
            return 'cat', 'pig', 'rhino'

        # Multiple Return Value Flag Subset

        result_2 = registry.build_out(FLAGS.PETS | FLAGS.FARM_ANIMALS)
        self.assertEqual(set(result_2.keys()), set(['pets', 'farm']))

        FLAGS = Flags('ONE')
        registry = FlagRegistry()

        @registry.register(flag=FLAGS.ONE)
        def method_one():
            return dict(tanya='redAlert')

        # Let the registry build our results dictionary. (Lacks start_with)
        # Use the default value for pass_dictionary (False)

        result_3 = registry.build_out(FLAGS.ONE)
        self.assertEqual(result_3, dict(tanya='redAlert'))

        # Pass in our own results dictionary (start_with=somedict)
        # Use the default value for pass_dictionary (False)

        somedict = dict(somekey='asdf', anotherkey='defg')
        result_4 = registry.build_out(FLAGS.ONE, start_with=somedict)
        self.assertEqual(set(result_4.keys()), set(['tanya', 'somekey', 'anotherkey']))

        # Pass in our own results dictionary (somedict=somedict)
        # Set pass_dictionary to True

        FLAGS = Flags('WINNER')
        registry = FlagRegistry()

        @registry.register(flag=FLAGS.WINNER)
        def method_winner(data):
            return dict(winner=data['name'])

        somedict = dict(name='george')
        result_4 = registry.build_out(FLAGS.WINNER, start_with=somedict, pass_datastructure=True)
        self.assertEqual(result_4, dict(winner='george', name='george'))

        # Let the registry build our results dictionary. (Lacks start_with)
        # Set pass_datastructure to True

        FLAGS = Flags('Cookies')
        registry = FlagRegistry()

        @registry.register(flag=FLAGS.Cookies)
        def method_cookies(data):
            return dict(cookies_remaining=len(data.keys()))

        result_4 = registry.build_out(FLAGS.ALL, pass_datastructure=True)
        self.assertEqual(result_4, dict(cookies_remaining=0))

        # Set pass_datastructure=True
        # Set starts_with
        # Also send starting_dict in *args
        # Make sure the registry doesn't send two copies of data to the method.

        FLAGS = Flags('ACK')
        registry = FlagRegistry()

        @registry.register(flag=FLAGS.ACK, key='salutation')
        def some_salutation(data):
            return data['hello']

        starting_dict = dict(hello="goodbye")
        result = registry.build_out(FLAGS.ALL, starting_dict, pass_datastructure=True, start_with=starting_dict)
        self.assertEqual(result, dict(hello='goodbye', salutation='goodbye'))

        # Dependent Method
        # Set pass_datastructure=True
        # Set starts_with
        # Also send starting_dict in *args
        # Make sure the registry doesn't send two copies of data to the method.

        FLAGS = Flags('PEOPLE', 'HOBBIES')
        registry = FlagRegistry()

        @registry.register(flag=FLAGS.PEOPLE, key='people')
        def method_people1(*args):
            return dict(simon='123', george='234')

        @registry.register(flag=FLAGS.HOBBIES, depends_on=FLAGS.PEOPLE, key='hobbies')
        def method_hobbies1(result):
            hobbies = {
                '123': ['mountain biking', 'skiing'],
                '234': ['snail collecting', 'roaring like a dinosaur']}

            return_value = dict()
            for person, uid in result['people'].items():
                return_value[person] = hobbies.get(uid)

            return return_value

        starting_dict = dict(hello="goodbye")
        result = registry.build_out(FLAGS.ALL, starting_dict, pass_datastructure=True, start_with=starting_dict)
        self.assertEqual(result, dict(
            hello='goodbye',
            people=dict(simon='123', george='234'),
            hobbies=dict(simon=['mountain biking', 'skiing'], george=['snail collecting', 'roaring like a dinosaur'])))