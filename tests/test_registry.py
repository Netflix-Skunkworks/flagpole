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
            registry._do_method_pass([method_one, method_two], 0, dict(), flags=FLAGS.ONE | FLAGS.TWO)
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
        def method_two():
            return 2

        result = dict()
        next_method_queue, executed_flag = registry._do_method_pass(
            [method_two, method_one], 0, result, flags=FLAGS.ONE | FLAGS.TWO)

        self.assertEqual(len(next_method_queue), 1) 
        self.assertEqual(executed_flag, FLAGS.ONE)
        self.assertEqual(set(result.keys()), set(['one']))
        
        next_method_queue, executed_flag = registry._do_method_pass(
            next_method_queue, executed_flag, result, flags=FLAGS.ONE | FLAGS.TWO)
            
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
          
        result = dict() 
        registry.build_out(result, FLAGS.PEOPLE, result)
        
        self.assertEqual(result, dict(people=dict(simon='123', george='234')))
        
        result = dict() 
        registry.build_out(result, FLAGS.HOBBIES, result)
        
        self.assertEqual(result, dict(
            people=dict(simon='123', george='234'),
            hobbies=dict(simon=['mountain biking', 'skiing'], george=['snail collecting', 'roaring like a dinosaur'])))

        result_1 = dict()
        registry.build_out(result_1, FLAGS.PEOPLE | FLAGS.HOBBIES, result_1)
        self.assertEqual(result, result_1)
        
        FLAGS = Flags('PETS', 'FARM_ANIMALS', 'WILD_ANIMALS')
        registry = FlagRegistry()

        @registry.register(
            flag=(FLAGS.PETS, FLAGS.FARM_ANIMALS, FLAGS.WILD_ANIMALS),
            key=('pets', 'farm', 'wild')) 
        def some_method():
            return 'cat', 'pig', 'rhino'

        result_2 = dict() 
        registry.build_out(result_2, FLAGS.PETS | FLAGS.FARM_ANIMALS)
        
        self.assertEqual(set(result_2.keys()), set(['pets', 'farm']))
        
        FLAGS = Flags('ONE')
        registry = FlagRegistry()

        @registry.register(flag=FLAGS.ONE)
        def method_one():
            return dict(tanya='redAlert')
            
        result_3 = dict() 
        registry.build_out(result_3, FLAGS.ONE)
        
        self.assertEqual(result_3, dict(tanya='redAlert'))