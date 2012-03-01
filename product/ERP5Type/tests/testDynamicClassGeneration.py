##############################################################################
#
# Copyright (c) 2010 Nexedi SARL and Contributors. All Rights Reserved.
#                    Nicolas Dumazet <nicolas.dumazet@nexedi.com>
#                    Arnaud Fontaine <arnaud.fontaine@nexedi.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsibility of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# guarantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.
#
##############################################################################

import gc
import unittest
import transaction

from persistent import Persistent
from Products.ERP5Type.dynamic.portal_type_class import synchronizeDynamicModules
from Products.ERP5Type.tests.ERP5TypeTestCase import ERP5TypeTestCase
from Products.ERP5Type.tests.backportUnittest import expectedFailure, skip
from Products.ERP5Type.Core.PropertySheet import PropertySheet as PropertySheetDocument

from zope.interface import Interface, implementedBy

class TestPortalTypeClass(ERP5TypeTestCase):
  def getBusinessTemplateList(self):
    return 'erp5_base',

  def testMigrateOldObject(self):
    """
    Check migration of persistent objects with old classes
    like Products.ERP5(Type).Document.Person.Person
    """
    from Products.ERP5Type.Document.Person import Person
    person_module = self.portal.person_module
    connection = person_module._p_jar
    newId = self.portal.person_module.generateNewId

    def unload(id):
      oid = person_module._tree[id]._p_oid
      person_module._tree._p_deactivate()
      connection._cache.invalidate(oid)
      gc.collect()
      # make sure we manage to remove the object from memory
      assert connection._cache.get(oid, None) is None
      return oid

    def check(migrated):
      klass = old_object.__class__
      self.assertEqual(klass.__module__,
        migrated and 'erp5.portal_type' or 'Products.ERP5.Document.Person')
      self.assertEqual(klass.__name__, 'Person')
      self.assertEqual(klass.__setstate__ is Persistent.__setstate__, migrated)

    # Import a .xml containing a Person created with an old
    # Products.ERP5Type.Document.Person.Person type
    self.importObjectFromFile(person_module, 'non_migrated_person.xml')
    transaction.commit()
    unload('non_migrated_person')
    old_object = person_module.non_migrated_person
    # object unpickling should have instanciated a new style object directly
    check(1)

    obj_id = newId()
    person_module._setObject(obj_id, Person(obj_id))
    transaction.commit()
    unload(obj_id)
    old_object = person_module[obj_id]
    # From now on, everything happens as if the object was a old, non-migrated
    # object with an old Products.ERP5(Type).Document.Person.Person
    check(0)
    # reload the object
    old_object._p_activate()
    check(1)
    # automatic migration is not persistent
    old_object = None
    # (note we get back the object directly from its oid to make sure we test
    # the class its pickle and not the one in its container)
    old_object = connection.get(unload(obj_id))
    check(0)

    # Test persistent migration
    old_object.migrateToPortalTypeClass()
    old_object = None
    transaction.commit()
    old_object = connection.get(unload(obj_id))
    check(1)
    # but the container still have the old class
    old_object = None
    unload(obj_id)
    old_object = person_module[obj_id]
    check(0)

    # Test persistent migration of containers
    obj_id = newId()
    person_module._setObject(obj_id, Person(obj_id))
    transaction.commit()
    unload(obj_id)
    person_module.migrateToPortalTypeClass()
    transaction.commit()
    unload(obj_id)
    old_object = person_module[obj_id]
    check(1)
    # not recursive by default
    old_object = None
    old_object = connection.get(unload(obj_id))
    check(0)

    # Test recursive migration
    old_object = None
    unload(obj_id)
    person_module.migrateToPortalTypeClass(True)
    transaction.commit()
    old_object = connection.get(unload(obj_id))
    check(1)

  def testChangeMixin(self):
    """
    Take an existing object, change the mixin definitions of its portal type.
    Check that the new methods are there.
    """
    portal = self.getPortal()
    person_module = portal.person_module
    person = person_module.newContent(id='John Dough', portal_type='Person')

    person_type = portal.portal_types.Person
    self.assertEquals(person_type.getTypeMixinList() or [], [])

    try:
      self.assertEquals(getattr(person, 'asText', None), None)
      # just use a mixin/method that Person does not have yet
      person_type.setTypeMixin('TextConvertableMixin')

      transaction.commit()

      self.assertNotEquals(getattr(person, 'asText', None), None)
    finally:
      # reset the type
      person_type.setTypeMixin(None)
      transaction.commit()

  def testChangeDocument(self):
    """
    Take an existing object, change its document class
    Check that the new methods are there.
    """
    portal = self.getPortal()
    person_module = portal.person_module
    person = person_module.newContent(id='Eva Dough', portal_type='Person')

    person_type = portal.portal_types.Person
    self.assertEquals(person_type.getTypeClass(), 'Person')

    try:
      self.assertEquals(getattr(person, 'getCorporateName', None), None)
      # change the base type class
      person_type.setTypeClass('Organisation')

      transaction.commit()

      self.assertNotEquals(getattr(person, 'getCorporateName', None), None)
    finally:
      # reset the type
      person_type.setTypeClass('Person')
      transaction.commit()

  def testTempPortalType(self):
    newType = self.portal.portal_types.newContent
    new_type_list = [newType(portal_type='Base Type', type_class='Folder',
                             type_filter_content_type=False).getId()
                     for i in (0, 1)]
    newDocument = self.portal.newContent(self.id(), 'Folder').newContent
    for temp_first, portal_type in enumerate(new_type_list):
      obj = newDocument(portal_type='Folder', temp_object=temp_first)
      obj.newContent('file', portal_type)
      obj.file.aq_base
      obj = newDocument(portal_type='Folder', temp_object=not temp_first)
      obj.newContent('file', portal_type)
      obj.file.aq_base

  def testBoundMethodCaching(self):
    """Test that it is safe to cache a bound method during a transaction

    This test currently fails with the following exception:
      TypeError: unbound method newContent() must be called with FolderMixIn
                 instance as first argument (got Folder instance instead)

    What is the scope of this failure ? Is this test a realistic use case ?
    Is there anyway to reset dynamic classes without triggering this error ?
    Or do we need to reset the fewest classes as possible ?
    """
    newDocument = self.portal.newContent(self.id(), 'Folder').newContent
    self.portal.portal_types.resetDynamicDocuments()
    newDocument(portal_type='Folder')

  def testInterfaces(self):
    types_tool = self.portal.portal_types

    # a new interface
    class IForTest(Interface):
      pass
    from Products.ERP5Type import interfaces
    interfaces.IForTest = IForTest


    # one new type
    dummy_type = types_tool.newContent('InterfaceTestType',
                                       'Base Type')
    # implementing IForTest
    dummy_type.edit(type_class='Person',
                    type_interface_list=['IForTest',],)
    transaction.commit()

    from erp5.portal_type import InterfaceTestType

    # it's necessary to load the class
    # to have a correct list of interfaces
    implemented_by = list(implementedBy(InterfaceTestType))
    self.failIf(IForTest in implemented_by)
    InterfaceTestType.loadClass()

    implemented_by = list(implementedBy(InterfaceTestType))
    self.assertTrue(IForTest in implemented_by,
                    'IForTest not in %s' % implemented_by)

    InterfaceTestType.restoreGhostState()
    implemented_by = list(implementedBy(InterfaceTestType))
    self.failIf(IForTest in implemented_by)

  def testClassHierarchyAfterReset(self):
    """
    Check that after a class reset, the class hierarchy is unchanged until
    un-ghostification happens. This is very important for multithreaded
    environments:
      Thread A. reset dynamic classes
      Thread B. in Folder code for instance: CMFBTreeFolder.method(self)

    If a reset happens before the B) method call, and does not keep the
    correct hierarchy (for instance Folder superclass is removed from
    the mro()), a TypeError might be raised:
      "method expected CMFBTreeFolder instance, got erp5.portal_type.xxx
      instead"

    This used to be broken because the ghost state was only what is called
    lazy_class.InitGhostBase: a "simple" subclass of ERP5Type.Base
    """
    name = "testClassHierarchyAfterReset Module"
    types_tool = self.portal.portal_types

    ptype = types_tool.newContent(id=name, type_class="Folder")
    transaction.commit()
    module_class = types_tool.getPortalTypeClass(name)
    module_class.loadClass()

    # first manually reset and check that everything works
    from Products.ERP5Type.Core.Folder import Folder
    self.assertTrue(issubclass(module_class, Folder))
    synchronizeDynamicModules(self.portal, force=True)
    self.assertTrue(issubclass(module_class, Folder))

    # then change the type value to something not descending from Folder
    # and check behavior
    ptype.setTypeClass('Address')

    # while the class has not been reset is should still descend from Folder
    self.assertTrue(issubclass(module_class, Folder))
    # finish transaction and trigger workflow/DynamicModule reset
    transaction.commit()
    # while the class has not been unghosted it's still a Folder
    self.assertTrue(issubclass(module_class, Folder))
    # but it changes as soon as the class is loaded
    module_class.loadClass()
    self.assertFalse(issubclass(module_class, Folder))

  def testAttributeValueComputedFromAccessorHolderList(self):
    """
    Check that attributes such as constraints and _categories,
    containing respectively all the constraints and categories define
    on their Property Sheets, loads the portal type class as some
    static getters (for example getInstanceBaseCategoryList() use
    _categories directly)
    """
    import erp5.portal_type

    synchronizeDynamicModules(self.portal, force=True)
    self.assertTrue(erp5.portal_type.Person.__isghost__)
    self.assertTrue('constraints' not in erp5.portal_type.Person.__dict__)

    getattr(erp5.portal_type.Person, 'constraints')
    self.assertTrue(not erp5.portal_type.Person.__isghost__)
    self.assertTrue('constraints' in erp5.portal_type.Person.__dict__)

    synchronizeDynamicModules(self.portal, force=True)
    self.assertTrue(erp5.portal_type.Person.__isghost__)
    self.assertTrue('_categories' not in erp5.portal_type.Person.__dict__)

    getattr(erp5.portal_type.Person, '_categories')
    self.assertTrue(not erp5.portal_type.Person.__isghost__)
    self.assertTrue('_categories' in erp5.portal_type.Person.__dict__)

class TestZodbPropertySheet(ERP5TypeTestCase):
  """
  XXX: WORK IN PROGRESS
  """
  def getBusinessTemplateList(self):
    return 'erp5_base',

  def _newStandardProperty(self, operation_type):
    """
    Create a new Standard Property within test Property Sheet
    """
    self.test_property_sheet.newContent(
      portal_type='Standard Property',
      reference='test_standard_property_' + operation_type,
      property_default='python: "test_default_value"',
      elementary_type='string')

  def _newAcquiredProperty(self, operation_type):
    """
    Create a new Acquired Property within test Property Sheet
    """
    self.test_property_sheet.newContent(
      portal_type='Acquired Property',
      reference='test_acquired_property_' + operation_type,
      elementary_type='content',
      storage_id='default_address',
      acquisition_mask_value=True,
      acquisition_base_category=('subordination',),
      acquisition_portal_type="python: ('Organisation',)",
      acquisition_accessor_id='getDefaultAddressValue',
      content_portal_type="python: ('Address',)",
      content_acquired_property_id=('street_address',))

  def _newCategoryTree(self, base_category_id, operation_type):
    """
    Create new categories for the tests (for the category accessors to
    be created, it's necessary that the category properties referenced
    in the web-based Property Sheet exist)
    """
    new_base_category = self.getPortal().portal_categories.newContent(
      id=base_category_id, portal_type='Base Category')

    # Create a dummy sub-category
    new_base_category.newContent(reference='sub_category1',
                                 portal_type='Category')

    new_base_category.newContent(reference='sub_category2',
                                 portal_type='Category')

    if operation_type == 'change':
      self.getPortal().portal_categories.newContent(
        id=base_category_id + '_renamed',
        portal_type='Base Category')

  def _newCategoryProperty(self, operation_type):
    """
    Create a new Category Property within test Property Sheet
    """
    category_id = 'test_category_property_' + operation_type

    self._newCategoryTree(category_id, operation_type)

    self.test_property_sheet.newContent(
      reference=category_id,
      portal_type='Category Property')

  def _newDynamicCategoryProperty(self, operation_type):
    """
    Create a new Dynamic Category Property within test Property Sheet
    """
    category_id = 'test_dynamic_category_property_' + operation_type

    self._newCategoryTree(category_id, operation_type)

    expression = "python: ('%s',)" % category_id

    self.test_property_sheet.newContent(
      portal_type='Dynamic Category Property',
      category_expression=expression,
      reference=category_id)

  def _newPropertyExistenceConstraint(self):
    """
    Create a new Property Existence Constraint within test Property
    Sheet
    """
    self.test_property_sheet.newContent(
      reference='test_property_existence_constraint',
      portal_type='Property Existence Constraint',
      constraint_property_list=('test_standard_property_constraint',))

  def _newCategoryExistenceConstraint(self):
    """
    Create a new Category Existence Constraint within test Property
    Sheet
    """
    self._newCategoryProperty('constraint')

    self.test_property_sheet.newContent(
      reference='test_category_existence_constraint',
      portal_type='Category Existence Constraint',
      constraint_base_category_list=('test_category_property_constraint',))
      # XXX
      # constraint_portal_type=('TODO',))

  def _newAttributeEqualityConstraint(self):
    """
    Create a new Attribute Equality Constraint within test Property
    Sheet
    """
    # For testing primitive type as attribute value
    self.test_property_sheet.newContent(
      reference='test_attribute_equality_constraint',
      portal_type='Attribute Equality Constraint',
      constraint_attribute_name='title',
      constraint_attribute_value='python: "my_valid_title"')

    # For testing list type as attribute value
    self.test_property_sheet.newContent(
      reference='test_attribute_list_equality_constraint',
      portal_type='Attribute Equality Constraint',
      constraint_attribute_name='categories_list',
      constraint_attribute_value='python: ("sub_category1", "sub_category2")')

  def _newContentExistenceConstraint(self):
    """
    Create a new Content Existence Constraint within test Property
    Sheet
    """
    self.test_property_sheet.newContent(
      reference='test_content_existence_constraint',
      portal_type='Content Existence Constraint',
      constraint_portal_type='python: ("Test Document")')

  def _newCategoryMembershipArityConstraint(self,
                                            reference,
                                            use_acquisition=False):
    """
    Create a new Category Membership Arity Constraint within test
    Property Sheet (with or without acquisition)
    """
    self.getPortal().portal_categories.newContent(
      id=reference, portal_type='Base Category')

    self.test_property_sheet.newContent(
      reference=reference,
      portal_type='Category Membership Arity Constraint',
      min_arity=1,
      max_arity=1,
      use_acquisition=use_acquisition,
      constraint_portal_type="python: ('Test Migration',)",
      constraint_base_category=(reference,))

  def _newCategoryRelatedMembershipArityConstraint(self):
    """
    Create a new Category Related Membership Arity Constraint within
    test Property Sheet, using an existing Base Category because
    creating a new Base Category would involve clearing up the cache
    """
    self.test_property_sheet.newContent(
      reference='test_category_related_membership_arity_constraint',
      portal_type='Category Related Membership Arity Constraint',
      min_arity=1,
      max_arity=1,
      constraint_portal_type="python: ('Test Migration',)",
      constraint_base_category=('gender',))

  def _newTALESConstraint(self):
    """
    Create a new TALES Constraint within test Property Sheet
    """
    self.test_property_sheet.newContent(
      reference='test_tales_constraint',
      portal_type='TALES Constraint',
      expression='python: object.getTitle() == "my_tales_constraint_title"')

  def _newPropertyTypeValidityConstraint(self):
    """
    Create a new Property Type Validity Constraint within test
    Property Sheet
    """
    self.test_property_sheet.newContent(
      reference='test_property_type_validity_constraint',
      portal_type='Property Type Validity Constraint')

  def afterSetUp(self):
    """
    Create a test Property Sheet (and its properties)
    """
    portal = self.getPortal()

    # Create the test Property Sheet
    try:
      self.test_property_sheet = portal.portal_property_sheets.TestMigration
      do_create = False
    except AttributeError:
      self.test_property_sheet = \
        portal.portal_property_sheets.newContent(id='TestMigration',
                                                 portal_type='Property Sheet')
      do_create = True

    if do_create:
      # Create a new Standard Property to test constraints and a
      # Property Existence Constraint in the test Property Sheet
      self._newStandardProperty('constraint')
      self._newPropertyExistenceConstraint()

      # Create a Category Existence Constraint in the test Property
      # Sheet
      self._newCategoryExistenceConstraint()

      # Create an Attribute Equality Constraint in the test Property
      # Sheet
      self._newAttributeEqualityConstraint()

      # Create a Content Existence Constraint in the test Property
      # Sheet
      self._newContentExistenceConstraint()

      # Create a Category Membership Arity Constraint without
      # acquisition in the test Property Sheet
      self._newCategoryMembershipArityConstraint(
        'test_category_membership_arity_constraint')

      # Create a Category Membership Arity Constraint with acquisition
      # in the test Property Sheet
      self._newCategoryMembershipArityConstraint(
        'test_category_membership_arity_constraint_with_acquisition',
        use_acquisition=True)

      # Create a Category Related Membership Arity Constraint in the
      # test Property Sheet
      self._newCategoryRelatedMembershipArityConstraint()

      # Create a TALES Constraint in the test Property Sheet
      self._newTALESConstraint()

      # Create a Property Type Validity Constraint in the test Property Sheet
      self._newPropertyTypeValidityConstraint()

      # Create all the test Properties
      for operation_type in ('change', 'delete', 'assign'):
        self._newStandardProperty(operation_type)
        self._newAcquiredProperty(operation_type)
        self._newCategoryProperty(operation_type)
        self._newDynamicCategoryProperty(operation_type)

    # Bind all test properties to this instance, so they can be
    # accessed easily in further tests
    for property in self.test_property_sheet.contentValues():
      setattr(self, property.getReference(), property)

    # Create a Portal Type for the tests, this is necessary, otherwise
    # there will be no accessor holder generated
    try:
      self.test_portal_type = getattr(portal.portal_types, 'Test Migration')
    except AttributeError:
      self.test_portal_type = portal.portal_types.newContent(
        id='Test Migration',
        portal_type='Base Type',
        type_class='Folder',
        type_property_sheet_list=('TestMigration',),
        type_base_category_list=('test_category_existence_constraint',),
        type_filter_content_type=False)
    # Create a Portal Type for subobject of Test Migration
    try:
      self.test_subobject_portal_type = getattr(portal.portal_types, 'Test Document')
    except AttributeError:
      self.test_subobject_portal_type = portal.portal_types.newContent(
        id='Test Document',
        portal_type='Base Type',
        type_class='Folder',
        type_filter_content_type=False)
      self.test_portal_type.setTypeAllowedContentTypeList(['Test Document'])

    # Create a test module, meaningful to force generation of
    # TestMigration accessor holders and check the constraints
    try:
      self.test_module = getattr(portal, 'Test Migration')
    except AttributeError:
      self.test_module = portal.newContent(id='Test Migration',
                                           portal_type='Test Migration')

    # Make sure there is no pending transaction which could interfere
    # with the tests
    transaction.commit()
    self.tic()

    # Ensure that erp5.acessor_holder is empty
    synchronizeDynamicModules(portal, force=True)

  def _forceTestAccessorHolderGeneration(self):
    """
    Force generation of TestMigration accessor holder by accessing any
    accessor, which will run the interaction workflow trigger, on
    commit at the latest
    """
    transaction.commit()
    self.test_module.getId()

  def testAssignUnassignZodbPropertySheet(self):
    """
    From an existing portal type, assign ZODB Property Sheets and
    check that
    """
    import erp5

    portal = self.getPortal()
    person_type = portal.portal_types.Person

    self.failIf('TestMigration' in person_type.getTypePropertySheetList())

    new_person = None
    try:
      # Assign ZODB test Property Sheet to the existing Person type
      # and create a new Person, this should generate the test
      # accessor holder which should be in the Person type inheritance
      person_type.setTypePropertySheetList('TestMigration')

      transaction.commit()

      self.assertTrue('TestMigration' in person_type.getTypePropertySheetList())

      # The accessor holder will be generated once the new Person will
      # be created as Person type has test Property Sheet
      self.failIfHasAttribute(erp5.accessor_holder.property_sheet,
                              'TestMigration')

      new_person = portal.person_module.newContent(
        id='testAssignZodbPropertySheet', portal_type='Person')

      self.assertHasAttribute(erp5.accessor_holder.property_sheet,
                              'TestMigration')

      self.assertTrue(erp5.accessor_holder.property_sheet.TestMigration in \
                      erp5.portal_type.Person.mro())

      # Check that the accessors have been properly created for all
      # the properties of the test Property Sheet and set a new value
      # to make sure that everything is fine
      #
      # Standard Property
      self.assertHasAttribute(new_person, 'setTestStandardPropertyAssign')

      self.assertEquals(new_person.getTestStandardPropertyAssign(),
                        "test_default_value")

      new_person.setTestStandardPropertyAssign('value')

      self.assertEquals(new_person.getTestStandardPropertyAssign(), 'value')

      # Acquired Property
      self.assertHasAttribute(
        new_person, 'setDefaultTestAcquiredPropertyAssignStreetAddress')

      new_person.setDefaultTestAcquiredPropertyAssignStreetAddress('value')

      self.assertHasAttribute(new_person, 'default_address')
      self.assertHasAttribute(new_person.default_address, 'getDefaultAddress')
      self.failIfEqual(None, new_person.default_address.getDefaultAddress())

      self.assertEquals(
        new_person.getDefaultTestAcquiredPropertyAssignStreetAddress(),
        'value')

      # Category Property
      self.assertHasAttribute(new_person, 'setTestCategoryPropertyAssign')

      new_person.setTestCategoryPropertyAssign('sub_category1')

      self.assertEquals(new_person.getTestCategoryPropertyAssign(),
                        'sub_category1')

      # Dynamic Category Property
      self.assertHasAttribute(new_person,
                              'setTestDynamicCategoryPropertyAssign')

      new_person.setTestDynamicCategoryPropertyAssign('sub_category1')

      self.assertEquals(new_person.getTestDynamicCategoryPropertyAssign(),
                        'sub_category1')

    finally:
      # Perform a commit here because Workflow interactions keeps a
      # TransactionalVariable whose key is computed from the ID of the
      # workflow and the ID of the interaction and where the value is
      # a boolean stating whether the transition method has already
      # been called before.  Thus, the next statement may not reset
      # erp5.accessor_holder as loading Person portal type calls
      # '_setType*'
      transaction.commit()

      person_type.setTypePropertySheetList(())

      if new_person is not None:
        portal.person_module.deleteContent(new_person.getId())

      new_person = None

    # Check that the new-style Property Sheet has been properly
    # unassigned by creating a new person in Person module
    transaction.commit()

    self.failIf('TestMigration' in person_type.getTypePropertySheetList())

    try:
      new_person = portal.person_module.newContent(
        id='testAssignZodbPropertySheet', portal_type='Person')

      self.failIfHasAttribute(erp5.accessor_holder.property_sheet, 'TestMigration')
      self.failIfHasAttribute(new_person, 'getTestStandardPropertyAssign')

    finally:
      if new_person is not None:
        portal.person_module.deleteContent(new_person.getId())

  def _checkAddPropertyToZodbPropertySheet(self,
                                          new_property_function,
                                          added_accessor_name):
    import erp5.accessor_holder.property_sheet

    self.failIfHasAttribute(erp5.accessor_holder.property_sheet,
                            'TestMigration')

    new_property_function('add')
    self._forceTestAccessorHolderGeneration()

    self.assertHasAttribute(erp5.accessor_holder.property_sheet,
                            'TestMigration')

    self.assertHasAttribute(erp5.accessor_holder.property_sheet.TestMigration,
                            added_accessor_name)

  def testAddStandardPropertyToZodbPropertySheet(self):
    """
    Take an existing new-style Property Sheet, add a new Standard
    Property and check that it has been properly added
    """
    self._checkAddPropertyToZodbPropertySheet(
      self._newStandardProperty,
      'getTestStandardPropertyAdd')

  def testAddAcquiredPropertyToZodbPropertySheet(self):
    """
    Take an existing new-style Property Sheet, add a new Acquired
    Property and check that it has been properly added
    """
    self._checkAddPropertyToZodbPropertySheet(
      self._newAcquiredProperty,
      'getDefaultTestAcquiredPropertyAddStreetAddress')

  def testAddCategoryPropertyToZodbPropertySheet(self):
    """
    Take an existing ZODB Property Sheet, add a new Category Property
    and check that it has been properly added
    """
    self._checkAddPropertyToZodbPropertySheet(
      self._newCategoryProperty,
      'getTestCategoryPropertyAdd')

  def testAddDynamicCategoryPropertyToZodbPropertySheet(self):
    """
    Take an existing ZODB Property Sheet, add a new Dynamic Category
    Property and check that it has been properly added
    """
    self._checkAddPropertyToZodbPropertySheet(
      self._newDynamicCategoryProperty,
      'getTestDynamicCategoryPropertyAdd')

  def _checkChangePropertyOfZodbPropertySheet(self,
                                             change_setter_func,
                                             new_value,
                                             changed_accessor_name):
    import erp5.accessor_holder.property_sheet

    self.failIfHasAttribute(erp5.accessor_holder.property_sheet,
                            'TestMigration')

    change_setter_func(new_value)
    self._forceTestAccessorHolderGeneration()

    self.assertHasAttribute(erp5.accessor_holder.property_sheet,
                            'TestMigration')

    self.assertHasAttribute(erp5.accessor_holder.property_sheet.TestMigration,
                            changed_accessor_name)

  def testChangeStandardPropertyOfZodbPropertySheet(self):
    """
    Take the test Property Sheet, change the 'reference' field of a
    Standard Property and check that the accessor name has changed
    """
    self._checkChangePropertyOfZodbPropertySheet(
      self.test_standard_property_change.setReference,
      'test_standard_property_change_renamed',
      'getTestStandardPropertyChangeRenamed')

  def testChangeAcquiredPropertyOfZodbPropertySheet(self):
    """
    Take the test Property Sheet, change the 'reference' field of an
    Acquired Property and check that the accessor name has changed
    """
    self._checkChangePropertyOfZodbPropertySheet(
      self.test_acquired_property_change.setReference,
      'test_acquired_property_change_renamed',
      'getDefaultTestAcquiredPropertyChangeRenamedStreetAddress')

  def testChangeCategoryPropertyOfZodbPropertySheet(self):
    """
    Take the test Property Sheet, change the 'id' field of a Category
    Property to another existing category and check that the accessor
    name has changed
    """
    self._checkChangePropertyOfZodbPropertySheet(
      self.test_category_property_change.setReference,
      'test_category_property_change_renamed',
      'getTestCategoryPropertyChangeRenamed')

  def testChangeDynamicCategoryPropertyOfZodbPropertySheet(self):
    """
    Take the test Property Sheet, change the 'category_expression'
    field of a Dynamic Category Property to another existing category
    and check that the accessor name has changed
    """
    self._checkChangePropertyOfZodbPropertySheet(
      self.test_dynamic_category_property_change.setCategoryExpression,
      "python: ('test_dynamic_category_property_change_renamed',)",
      'getTestDynamicCategoryPropertyChangeRenamed')

  def _checkDeletePropertyFromZodbPropertySheet(self,
                                               property_id,
                                               accessor_name):
    """
    Delete the given property from the test Property Sheet and check
    whether its corresponding accessor is not there anymore
    """
    import erp5.accessor_holder.property_sheet

    self.failIfHasAttribute(erp5.accessor_holder, 'TestMigration')

    # Delete the property and force re-generation of TestMigration
    # accessor holder
    self.test_property_sheet.deleteContent(property_id)
    self._forceTestAccessorHolderGeneration()

    self.assertHasAttribute(erp5.accessor_holder.property_sheet, 'TestMigration')
    self.failIfHasAttribute(erp5.accessor_holder.property_sheet.TestMigration,
                            accessor_name)

  def testDeleteStandardPropertyFromZodbPropertySheet(self):
    """
    Take the test Property Sheet, delete a Standard Property and check
    that the accessor is not there anymore
    """
    self._checkDeletePropertyFromZodbPropertySheet(
      self.test_standard_property_delete.getId(),
      'getTestStandardPropertyDelete')

  def testDeleteAcquiredPropertyFromZodbPropertySheet(self):
    """
    Take the test Property Sheet, delete an Acquired Property and
    check that the accessor is not there anymore
    """
    self._checkDeletePropertyFromZodbPropertySheet(
      self.test_acquired_property_delete.getId(),
      'getTestAcquiredPropertyDelete')

  def testDeleteCategoryPropertyFromZodbPropertySheet(self):
    """
    Take the test Property Sheet, delete a Category Property and check
    that the accessor is not there anymore
    """
    self._checkDeletePropertyFromZodbPropertySheet(
      self.test_category_property_delete.getId(),
      'getTestCategoryPropertyDelete')

  def testDeleteDynamicCategoryPropertyFromZodbPropertySheet(self):
    """
    Take the test Property Sheet, delete a Category Property and check
    that the accessor is not there anymore
    """
    self._checkDeletePropertyFromZodbPropertySheet(
      self.test_dynamic_category_property_delete.getId(),
      'getTestDynamicCategoryPropertyDelete')

  def _getConstraintByReference(self, reference):
    for constraint in self.test_module.constraints:
      try:
        if constraint.getReference() == reference:
          return constraint
      except AttributeError:
        pass

    return None

  def _checkConstraint(self,
                       constraint_reference,
                       setter_function,
                       *args,
                       **kw):
    constraint = self._getConstraintByReference(constraint_reference)
    self.failIfEqual(None, constraint)

    # Use Base.checkConsistency!!
    # This is the standard interface which real users are always using.
    # Never call ConstraintMixin.checkConsistency directly in unit test.
    # You will miss serious bugs.
    self.assertEquals(1, len(self.test_module.checkConsistency(filter={'reference':constraint_reference})))

    setter_function(*args, **kw)
    self.assertEquals([], self.test_module.checkConsistency(filter={'reference':constraint_reference}))

  def testPropertyExistenceConstraint(self):
    """
    Take the test module and check whether the Property Existence
    Constraint is there. Until the property has been set to a value,
    the constraint should fail
    """
    # See ERP5Type.Base.Base.hasProperty()
    self._checkConstraint('test_property_existence_constraint',
                          self.test_module.setTestStandardPropertyConstraint,
                          'foobar')

  def testCategoryExistenceConstraint(self):
    """
    Take the test module and check whether the Property Existence
    Constraint is there. Until the category has been set to an
    existing category, the constraint should fail
    """
    self._checkConstraint('test_category_existence_constraint',
                          self.test_module.setTestCategoryPropertyConstraint,
                          'sub_category1')

  def testAttributeEqualityConstraint(self):
    """
    Take the test module and check whether the Attribute Equality
    Constraint is there. Until the attribute to be checked has been
    set to its expected value, the constraint should fail. The purpose
    is to test only primitive types (e.g. not list)
    """
    # As checkConsistency calls hasProperty before checking the value,
    # the property to be tested has to be set at least once (whatever
    # the value)
    self.test_module.setTitle('invalid_value')

    self._checkConstraint('test_attribute_equality_constraint',
                          self.test_module.setTitle,
                          'my_valid_title')

  def testAttributeListEqualityConstraint(self):
    """
    Take the test module and check whether the Attribute Equality
    Constraint is there. Until the attribute to be checked has been
    set to its expected value (a list of categories), the constraint
    should fail. The purpose is to test only list types

    @see testAttributeEqualityConstraint
    """
    self.test_module.setCategoryList(('sub_category1',))

    self._checkConstraint('test_attribute_list_equality_constraint',
                          self.test_module.setCategoryList,
                          ('sub_category1', 'sub_category2'))

  def testContentExistenceConstraint(self):
    """
    Take the test module and check whether the Test Document is there.
    Until there is at least one subobject of 'Test Module' whose Portal
    Type is 'Folder', the constraint should fail
    """
    self._checkConstraint('test_content_existence_constraint',
                          self.test_module.newContent,
                          id='Test Content Existence Constraint',
                          portal_type='Test Document')

  def testCategoryMembershipArityConstraint(self):
    """
    Take the test module and check whether the Category Membership
    Arity Constraint is there. Until a Base Category is set on the
    Test Module, the constraint should fail
    """
    self._checkConstraint('test_category_membership_arity_constraint',
                          self.test_module.setCategoryList,
                          ('test_category_membership_arity_constraint/'\
                           'Test Migration',))

  def testCategoryMembershipArityConstraintWithAcquisition(self):
    """
    Take the test module and check whether the Category Acquired
    Membership Arity Constraint is there. Until a Base Category is set
    on the Test Module, the constraint should fail

    XXX: Test with acquisition?
    """
    self._checkConstraint(
      'test_category_membership_arity_constraint_with_acquisition',
      self.test_module.setCategoryList,
      ('test_category_membership_arity_constraint_with_acquisition/Test Migration',))

  def testCategoryRelatedMembershipArityConstraint(self):
    """
    Take the test module and check whether the Category Related
    Membership Arity Constraint is there. Until a Base Category is set
    on the Test Module, the constraint should fail

    XXX: Test filter_parameter
    """
    constraint = self._getConstraintByReference(
      'test_category_related_membership_arity_constraint')

    self.failIfEqual(None, constraint)
    self.assertEquals(1, len(constraint.checkConsistency(self.test_module)))

    self.test_module.setCategoryList(('gender/Test Migration',))
    transaction.commit()
    self.tic()

    self.assertEquals([], constraint.checkConsistency(self.test_module))

  def testTALESConstraint(self):
    """
    Take the test module and check whether the TALES Constraint is
    there. Until the title of Test Module has been set to the expected
    value, the constraint should fail
    """
    self._checkConstraint('test_tales_constraint',
                          self.test_module.setTitle,
                          'my_tales_constraint_title')

  def testPropertyTypeValidityConstraint(self):
    """
    Take the test module and check whether the Property Type Validity
    Constraint is there, then set the title of Test Module to any
    value besides of a string. Until the title of Test Module has been
    set to any string, the constraint should fail
    """
    self.test_module.title = 123

    self._checkConstraint('test_property_type_validity_constraint',
                          self.test_module.setTitle,
                          'my_property_type_validity_constraint_title')

  def testConstraintAfterClosingZODBConnection(self):
    """
    Make sure that constraint works even if ZODB connection close.
    This test is added for the bug #20110628-ABAA76.
    """
    # Open new connection and add a new constraint.
    db = self.app._p_jar.db()
    con = db.open()
    app = con.root()['Application'].__of__(self.app.aq_parent)
    portal = app[self.getPortalName()]
    from Products.ERP5.ERP5Site import getSite, setSite
    old_site = getSite()
    setSite(portal)

    import erp5
    dummy = getattr(erp5.portal_type, 'TALES Constraint')(id='dummy')
    portal.portal_property_sheets.TestMigration._setObject('dummy', dummy)
    dummy = portal.portal_property_sheets.TestMigration.dummy
    dummy.edit(reference='test_dummy_constraint',
               expression='python: object.getTitle() == "my_tales_constraint_title"')
    dummy.Predicate_view()

    transaction.commit()

    # Recreate class with a newly added constraint
    synchronizeDynamicModules(portal, force=True)
    # Load test_module
    test_module = getattr(portal, 'Test Migration')
    test_module.objectValues()
    # Then close this new connection.
    transaction.abort()
    con.close()
    # This code depends on ZODB implementation.
    for i in db.pool.available[:]:
      if i[1] == con:
        db.pool.available.remove(i)
    db.pool.all.remove(con)
    del con

    # Back to the default connection.
    transaction.abort()
    self.app._p_jar._resetCache()
    setSite(old_site)

    # Call checkConsistency and make sure that ConnectionStateError does not occur.
    self.assert_(self.test_module.checkConsistency())

  def testAddEmptyProperty(self):
    """
    When users create properties in a PropertySheet, the property is
    first empty. Check that accessor generation can cope with such
    invalid properties
    """
    property_sheet_tool = self.portal.portal_property_sheets
    arrow = property_sheet_tool.Arrow
    person_module = self.portal.person_module
    person = person_module.newContent(portal_type="Person")

    # Action -> add Acquired Property
    arrow.newContent(portal_type="Acquired Property")
    # a user is doing this, so commit after each request
    transaction.commit()

    accessor = getattr(property_sheet_tool, "setTitle", None)
    # sites used to break at this point
    self.assertNotEquals(None, accessor)
    # try to create a Career, which uses Arrow Property Sheet
    try:
      person.newContent(portal_type="Career")
    except Exception:
      # Arrow property holder could not be created from the
      # invalid Arrow Property Sheet
      self.fail("Creating an empty Acquired Property raises an error")

    arrow.newContent(portal_type="Category Property")
    transaction.commit()
    try:
      person.newContent(portal_type="Career")
    except Exception:
      self.fail("Creating an empty Category Property raises an error")

    dynamic_category = arrow.newContent(portal_type="Dynamic Category Property")
    transaction.commit()
    try:
      person.newContent(portal_type="Career")
    except Exception:
      self.fail("Creating an empty Dynamic Category Property raises an error")

    arrow.newContent(portal_type="Property Existence Constraint")
    transaction.commit()
    try:
      person.newContent(portal_type="Career")
    except Exception:
      self.fail("Creating an empty Constraint raises an error")

  def testAddInvalidProperty(self):
    """
    Check that setting an invalid TALES Expression as a property
    attribute value does not raise any error

    XXX: For now, this test fails because the accessors generation
    going through Utils does catch errors when evaluating TALES
    Expression, but this will be addressed in per-property document
    accessors generation
    """
    arrow = self.portal.portal_property_sheets.Arrow
    person = self.portal.person_module.newContent(portal_type="Person")

    # be really nasty, and test that code is still foolproof (this
    # None value should never appear in an expression... unless the
    # method has a mistake)
    dynamic_category = arrow.newContent(
      portal_type="Dynamic Category Property",
      category_expression='python: ["foo", None, "region"]')

    transaction.commit()
    try:
      person.newContent(portal_type="Career")
    except Exception:
      self.fail("Creating a Category Expression with None as one of the "\
                "category ID raises an error")

    # Action -> add Acquired Property
    arrow.newContent(portal_type="Acquired Property",
                     acquisition_portal_type="python: ('foo', None)",
                     content_portal_type="python: ('goo', None)")
    # a user is doing this, so commit after each request
    transaction.commit()
    try:
      person.newContent(portal_type="Career")
    except Exception:
      self.fail("Creating an Acquired Property with invalid TALES expression "\
                "raises an error")

    # Check invalid syntax in TALES Expression, we check only for
    # DynamicCategoryProperty because it's exactly the same function
    # called for StandardProperty and AcquiredProperty, namely
    # evaluateExpressionFromString
    dynamic_category.setCategoryExpression('python: [')
    transaction.commit()
    try:
      person.newContent(portal_type="Career")
    except Exception:
      self.fail("Creating a Category Expression with syntax error raises "\
                "an error")

from Products.ERP5Type.Tool.ComponentTool import ComponentTool
ComponentTool._original_reset = ComponentTool.reset
ComponentTool._reset_performed = False

def assertResetNotCalled(*args, **kwargs):
  reset_performed = ComponentTool._original_reset(*args, **kwargs)
  if reset_performed:
    raise AssertionError("reset should not have been performed")

  return reset_performed

def assertResetCalled(*args, **kwargs):
  reset_performed = ComponentTool._original_reset(*args, **kwargs)
  if reset_performed:
    ComponentTool._reset_performed = True

  return reset_performed

import abc

from Products.ERP5Type.mixin.component import ComponentMixin
from Products.ERP5Type.tests.SecurityTestCase import SecurityTestCase
from App.config import getConfiguration

class _TestZodbComponent(SecurityTestCase):
  __metaclass__ = abc.ABCMeta

  def getBusinessTemplateList(self):
    return ('erp5_base',
            'erp5_core_component')

  def login(self, user_name='ERP5TypeTestCase', quiet=0):
    product_config = getattr(getConfiguration(), 'product_config', None)
    if product_config is None:
      class DummyDeveloperConfig(object):
        pass

      dummy_developer_config = DummyDeveloperConfig()
      dummy_developer_config.developer_list = [user_name]
      getConfiguration().product_config = {'erp5': dummy_developer_config}

    elif user_name not in product_config['erp5'].developer_list:
      product_config['erp5'].developer_list.append(user_name)

    return super(_TestZodbComponent, self).login(user_name, quiet)

  def afterSetUp(self):
    self._component_tool = self.getPortal().portal_components
    self._module = __import__(self._getComponentModuleName(),
                              fromlist=['erp5.component'])
    self._component_tool.reset(force=True, reset_portal_type=True)

  @abc.abstractmethod
  def _newComponent(self, reference, text_content, version='erp5'):
    pass

  @abc.abstractmethod
  def _getComponentModuleName(self):
    pass

  def _getComponentFullModuleName(self, module_name):
    return "%s.%s" % (self._getComponentModuleName(), module_name)

  def failIfModuleImportable(self, module_name):
    full_module_name = self._getComponentFullModuleName(module_name)

    try:
      __import__(full_module_name, fromlist=[self._getComponentModuleName()],
                 level=0)
    except ImportError:
      pass
    else:
      raise AssertionError("Component '%s' should not have been generated" % \
                             full_module_name)

  def assertModuleImportable(self, module_name):
    full_module_name = self._getComponentFullModuleName(module_name)

    try:
      __import__(full_module_name, fromlist=[self._getComponentModuleName()],
                 level=0)
    except ImportError:
      raise AssertionError("Component '%s' should have been generated" % \
                             full_module_name)

  def testValidateInvalidate(self):
    """
    The new Component should only be in erp5.component.XXX when validated,
    otherwise an AttributeError should be raised
    """
    test_component = self._newComponent(
      'TestValidateInvalidateComponent',
      'def foobar(*args, **kwargs):\n  return "ValidateInvalidate"')

    test_component.validate()
    transaction.commit()
    self.tic()

    self.assertModuleImportable('TestValidateInvalidateComponent')
    test_component.invalidate()
    transaction.commit()
    self.tic()
    self.failIfModuleImportable('TestValidateInvalidateComponent')

    test_component.validate()
    transaction.commit()
    self.tic()
    self.assertModuleImportable('TestValidateInvalidateComponent')

  def testReferenceWithReservedKeywords(self):
    """
    Check whether checkConsistency has been properly implemented for checking
    Component Reference field, e.g. no reserved keywords can be used
    """
    valid_reference = 'TestReferenceWithReservedKeywords'
    ComponentTool.reset = assertResetCalled
    try:
      component = self._newComponent(valid_reference,
                                     'def foobar(*args, **kwargs):\n  return 42')

      component.validate()
      transaction.commit()
      self.tic()

      self.assertEquals(ComponentTool._reset_performed, True)
    finally:
      ComponentTool.reset = ComponentTool._original_reset
      ComponentTool._reset_performed = False

    self.assertEquals(component.getValidationState(), 'validated')
    self.assertEquals(component.getErrorMessageList(), [])
    self.assertEquals(component.getReference(), valid_reference)
    self.assertEquals(component.getReference(validated_only=True), valid_reference)
    self.assertModuleImportable(valid_reference)

    invalid_reference_dict = {
      None: ComponentMixin._message_reference_not_set,
      'ReferenceReservedKeywords_version': ComponentMixin._message_invalid_reference,
      '_ReferenceReservedKeywords': ComponentMixin._message_invalid_reference,
      'find_module': ComponentMixin._message_invalid_reference,
      'load_module': ComponentMixin._message_invalid_reference}

    for invalid_reference, error_message in invalid_reference_dict.iteritems():
      ComponentTool.reset = assertResetNotCalled
      try:
        component.setReference(invalid_reference)
        transaction.commit()
        self.tic()
      finally:
        ComponentTool.reset = ComponentTool._original_reset

      self.assertEquals(component.getValidationState(), 'modified')
      error_list = component.getErrorMessageList()
      self.assertNotEquals(error_list, [])
      self.assertEquals(len(error_list), 1)
      self.assertEquals(error_message, error_list[0])
      self.assertEquals(component.getReference(), invalid_reference)
      self.assertEquals(component.getReference(validated_only=True), valid_reference)
      self._component_tool.reset(force=True, reset_portal_type=True)
      self.assertModuleImportable(valid_reference)

    ComponentTool.reset = assertResetCalled
    try:
      component.setReference(valid_reference)
      transaction.commit()
      self.tic()

      self.assertEquals(ComponentTool._reset_performed, True)
    finally:
      ComponentTool.reset = ComponentTool._original_reset
      ComponentTool._reset_performed = False

    self.assertEquals(component.getValidationState(), 'validated')
    self.assertEquals(component.getErrorMessageList(), [])
    self.assertEquals(component.getReference(), valid_reference)
    self.assertEquals(component.getReference(validated_only=True), valid_reference)
    self.assertModuleImportable(valid_reference)

  def testVersionWithReservedKeywords(self):
    """
    Check whether checkConsistency has been properly implemented for checking
    Component version field, e.g. no reserved keywords can be used
    """
    reference = 'TestVersionWithReservedKeywords'
    valid_version = 'erp5'
    ComponentTool.reset = assertResetCalled
    try:
      component = self._newComponent(reference,
                                     'def foobar(*args, **kwargs):\n  return 42',
                                     valid_version)

      component.validate()
      transaction.commit()
      self.tic()

      self.assertEquals(ComponentTool._reset_performed, True)
    finally:
      ComponentTool.reset = ComponentTool._original_reset
      ComponentTool._reset_performed = False

    self.assertEquals(component.getValidationState(), 'validated')
    self.assertEquals(component.getErrorMessageList(), [])
    self.assertEquals(component.getVersion(), valid_version)
    self.assertEquals(component.getVersion(validated_only=True), valid_version)
    self.assertModuleImportable(reference)

    invalid_version_dict = {
      '': ComponentMixin._message_version_not_set,
      '_TestVersionWithReservedKeywords': ComponentMixin._message_invalid_version}

    for invalid_version, error_message in invalid_version_dict.iteritems():
      ComponentTool.reset = assertResetNotCalled
      try:
        component.setVersion(invalid_version)
        transaction.commit()
        self.tic()
      finally:
        ComponentTool.reset = ComponentTool._original_reset

      self.assertEquals(component.getValidationState(), 'modified')
      error_list = component.getErrorMessageList()
      self.assertNotEquals(error_list, [])
      self.assertEquals(len(error_list), 1)
      self.assertEquals(error_message, error_list[0])
      self.assertEquals(component.getVersion(), invalid_version)
      self.assertEquals(component.getVersion(validated_only=True), valid_version)
      self._component_tool.reset(force=True, reset_portal_type=True)
      self.assertModuleImportable(reference)

    ComponentTool.reset = assertResetCalled
    try:
      component.setVersion(valid_version)
      transaction.commit()
      self.tic()

      self.assertEquals(ComponentTool._reset_performed, True)
    finally:
      ComponentTool.reset = ComponentTool._original_reset
      ComponentTool._reset_performed = False

    self.assertEquals(component.getValidationState(), 'validated')
    self.assertEquals(component.getErrorMessageList(), [])
    self.assertEquals(component.getVersion(), valid_version)
    self.assertEquals(component.getVersion(validated_only=True), valid_version)
    self.assertModuleImportable(reference)

  def testInvalidSourceCode(self):
    """
    Check whether checkConsistency has been properly implemented for checking
    Component source code field
    """
    valid_code = 'def foobar(*args, **kwargs):\n  return 42'
    ComponentTool.reset = assertResetCalled
    try:
      component = self._newComponent('TestComponentWithSyntaxError', valid_code)
      component.validate()
      transaction.commit()
      self.tic()

      self.assertEquals(ComponentTool._reset_performed, True)
    finally:
      ComponentTool.reset = ComponentTool._original_reset
      ComponentTool._reset_performed = False

    self.assertEquals(component.getValidationState(), 'validated')
    self.assertEquals(component.getErrorMessageList(), [])
    self.assertEquals(component.getTextContent(), valid_code)
    self.assertEquals(component.getTextContent(validated_only=True), valid_code)
    self.assertModuleImportable('TestComponentWithSyntaxError')

    invalid_code_dict = {
      None: ComponentMixin._message_text_content_not_set,
      'def foobar(*args, **kwargs)\n  return 42': 'Syntax error in source code:',
      'foobar': 'Source code:'}

    for invalid_code, error_message in invalid_code_dict.iteritems():
      ComponentTool.reset = assertResetNotCalled
      try:
        component.setTextContent(invalid_code)
        transaction.commit()
        self.tic()
      finally:
        ComponentTool.reset = ComponentTool._original_reset

      self.assertEquals(component.getValidationState(), 'modified')
      error_list = component.getErrorMessageList()
      self.assertNotEqual(error_list, [])
      self.assertEquals(len(error_list), 1)
      self.assertTrue(error_list[0].startswith(error_message))
      self.assertEquals(component.getTextContent(), invalid_code)
      self.assertEquals(component.getTextContent(validated_only=True), valid_code)
      self._component_tool.reset(force=True, reset_portal_type=True)
      self.assertModuleImportable('TestComponentWithSyntaxError')

    ComponentTool.reset = assertResetCalled
    try:
      component.setTextContent(valid_code)
      transaction.commit()
      self.tic()

      self.assertEquals(ComponentTool._reset_performed, True)
    finally:
      ComponentTool.reset = ComponentTool._original_reset
      ComponentTool._reset_performed = False

    self.assertEquals(component.getValidationState(), 'validated')
    self.assertEquals(component.getErrorMessageList(), [])
    self.assertEquals(component.getTextContent(), valid_code)
    self.assertEquals(component.getTextContent(validated_only=True), valid_code)
    self.assertModuleImportable('TestComponentWithSyntaxError')

  def testImportVersionedComponentOnly(self):
    component = self._newComponent(
      'TestImportedVersionedComponentOnly',
      """def foo(*args, **kwargs):
  return "TestImportedVersionedComponentOnly"
""")

    component.validate()
    transaction.commit()
    self.tic()

    top_module_name = self._getComponentModuleName()

    component_import = self._newComponent(
      'TestImportVersionedComponentOnly',
      """from %s.erp5_version.TestImportedVersionedComponentOnly import foo

def bar(*args, **kwargs):
  return foo(*args, **kwargs)
""" % top_module_name)

    component_import.validate()
    transaction.commit()
    self.tic()

    self.assertModuleImportable('TestImportVersionedComponentOnly')
    self.assertModuleImportable('erp5_version.TestImportedVersionedComponentOnly')

    top_module = __import__(top_module_name, level=0,
                            fromlist=[top_module_name])

    self.assertHasAttribute(
      top_module.erp5_version.TestImportedVersionedComponentOnly, 'foo')

    self.assertEquals(
      top_module.erp5_version.TestImportedVersionedComponentOnly.foo(),
      'TestImportedVersionedComponentOnly')

    self.failIfHasAttribute(top_module, 'TestImportedVersionedComponentOnly')

  def testVersionPriority(self):
    component_erp5_version = self._newComponent(
      'TestVersionPriority',
      """def function_foo(*args, **kwargs):
  return "TestERP5VersionPriority"
""")

    component_erp5_version.validate()
    transaction.commit()
    self.tic()

    component_foo_version = self._newComponent(
      'TestVersionPriority',
      """def function_foo(*args, **kwargs):
  return "TestFooVersionPriority"
""",
      'foo')

    component_foo_version.validate()
    transaction.commit()
    self.tic()

    self.assertModuleImportable('TestVersionPriority')
    self.assertModuleImportable('erp5_version.TestVersionPriority')
    self.failIfModuleImportable('foo_version.TestVersionPriority')

    top_module_name = self._getComponentModuleName()
    top_module = __import__(top_module_name, level=0,
                            fromlist=[top_module_name])

    self.assertHasAttribute(top_module.TestVersionPriority, 'function_foo')
    self.assertEquals(top_module.TestVersionPriority.function_foo(),
                      "TestERP5VersionPriority")

    from Products.ERP5.ERP5Site import getSite
    site = getSite()
    ComponentTool.reset = assertResetCalled
    priority_tuple = site.getVersionPriorityList()
    try:
      site.setVersionPriorityList(('foo',) + priority_tuple)
      transaction.commit()
      self.tic()

      self.assertEquals(ComponentTool._reset_performed, True)

      self.assertModuleImportable('TestVersionPriority')
      self.assertModuleImportable('erp5_version.TestVersionPriority')
      self.assertModuleImportable('foo_version.TestVersionPriority')

      self.assertHasAttribute(top_module.TestVersionPriority, 'function_foo')
      self.assertEquals(top_module.TestVersionPriority.function_foo(),
                        "TestFooVersionPriority")

    finally:
      ComponentTool.reset = ComponentTool._original_reset
      site.setVersionPriorityList(priority_tuple)
      transaction.commit()
      self.tic()

  def testDeveloperRoleSecurity(self):
    """
    XXX-arnau: test with different users and workflows
    """
    component = self._newComponent('TestDeveloperRoleSecurity',
                                   'def foo():\n  print "ok"')

    transaction.commit()
    self.tic()

    user_id = 'ERP5TypeTestCase'

    self.assertUserCanChangeLocalRoles(user_id, self._component_tool)
    self.assertUserCanModifyDocument(user_id, self._component_tool)
    self.assertUserCanDeleteDocument(user_id, self._component_tool)
    self.assertUserCanChangeLocalRoles(user_id, component)
    self.assertUserCanDeleteDocument(user_id, component)

    getConfiguration().product_config['erp5'].developer_list = []

    # Component Tool and the Component should be viewable by Manager
    self.assertUserCanViewDocument(user_id, self._component_tool)
    self.assertUserCanAccessDocument(user_id, self._component_tool)
    self.assertUserCanViewDocument(user_id, component)
    self.assertUserCanAccessDocument(user_id, component)

    # But nothing else should be permitted on Component Tool nor Component
    self.failIfUserCanAddDocument(user_id, self._component_tool)
    self.failIfUserCanModifyDocument(user_id, self._component_tool)
    self.failIfUserCanDeleteDocument(user_id, self._component_tool)
    self.failIfUserCanModifyDocument(user_id, component)
    self.failIfUserCanDeleteDocument(user_id, component)
    self.failIfUserCanChangeLocalRoles(user_id, component)

    getConfiguration().product_config['erp5'].developer_list = [user_id]

    self.assertUserCanChangeLocalRoles(user_id, self._component_tool)
    self.assertUserCanModifyDocument(user_id, self._component_tool)
    self.assertUserCanDeleteDocument(user_id, self._component_tool)
    self.assertUserCanChangeLocalRoles(user_id, component)
    self.assertUserCanModifyDocument(user_id, component)
    self.assertUserCanDeleteDocument(user_id, component)

from Products.ERP5Type.Core.ExtensionComponent import ExtensionComponent

class TestZodbExtensionComponent(_TestZodbComponent):
  def _newComponent(self, reference, text_content, version='erp5'):
    return self._component_tool.newContent(
      id='%s.%s.%s' % (self._getComponentModuleName(),
                       version + '_version',
                       reference),
      version=version,
      reference=reference,
      text_content=text_content,
      portal_type='Extension Component')

  def _getComponentModuleName(self):
    return ExtensionComponent._getDynamicModuleNamespace()

  def testExternalMethod(self):
    test_component = self._newComponent(
      'TestExternalMethodComponent',
      'def foobar(*args, **kwargs):\n  return 42')

    test_component.validate()
    transaction.commit()
    self.tic()

    self.assertModuleImportable('TestExternalMethodComponent')

    # Add an External Method using the Extension Component defined above and
    # check that it returns 42
    from Products.ExternalMethod.ExternalMethod import manage_addExternalMethod
    manage_addExternalMethod(self.getPortal(),
                             'TestExternalMethod',
                             'title',
                             'TestExternalMethodComponent',
                             'foobar')

    transaction.commit()
    self.tic()

    external_method = self.getPortal().TestExternalMethod
    self.assertEqual(external_method(), 42)

    # Add a Python Script with the External Method defined above and check
    # that it returns 42
    from Products.PythonScripts.PythonScript import manage_addPythonScript
    manage_addPythonScript(self.getPortal(), 'TestPythonScript')
    self.getPortal().TestPythonScript.write('return context.TestExternalMethod()')
    transaction.commit()
    self.tic()

    self.assertEqual(self.getPortal().TestPythonScript(), 42)

    # Invalidate the Extension Component
    test_component.invalidate()
    transaction.commit()
    self.tic()

    # XXX-arnau: perhaps the error message should be more meaningful
    try:
      external_method()
    except RuntimeError, e:
      self.assertEquals(e.message,
                        'external method could not be called because it is None')
    else:
      raise AssertionError("TestExternalMethod should not be callable")

from Products.ERP5Type.Core.DocumentComponent import DocumentComponent

class TestZodbDocumentComponent(_TestZodbComponent):
  def _newComponent(self, reference, text_content, version='erp5'):
    return self._component_tool.newContent(
      id='%s.%s.%s' % (self._getComponentModuleName(),
                       version + '_version', reference),
      reference=reference,
      version=version,
      text_content=text_content,
      portal_type='Document Component')

  def _getComponentModuleName(self):
    return DocumentComponent._getDynamicModuleNamespace()

  def testAssignToPortalTypeClass(self):
    from Products.ERP5.Document.Person import Person as PersonDocument

    self.failIfModuleImportable('TestPortalType')

    # Create a new Document Component inheriting from Person Document which
    # defines only one additional method (meaningful to make sure that the
    # class (and not the module) has been added to the class when the
    # TypeClass is changed)
    test_component = self._newComponent(
      'TestPortalType',
      """
from Products.ERP5Type.Document.Person import Person

class TestPortalType(Person):
  def test42(self):
    return 42
""")

    test_component.validate()
    transaction.commit()
    self.tic()

    # As TestPortalType Document Component has been validated, it should now
    # be available
    self.assertModuleImportable('TestPortalType')

    person_type = self.getPortal().portal_types.Person
    person_type_class = person_type.getTypeClass()
    self.assertEquals(person_type_class, 'Person')

    # Create a new Person
    person_module = self.getPortal().person_module
    person = person_module.newContent(id='Foo Bar', portal_type='Person')
    self.assertTrue(PersonDocument in person.__class__.mro())

    # There is no reason that TestPortalType Document Component has been
    # assigned to a Person, otherwise there is something really bad going on
    self.failIfHasAttribute(person, 'test42')
    self.assertFalse(self._module.TestPortalType in person.__class__.mro())

    # Reset Portal Type classes to ghost to make sure that everything is reset
    self._component_tool.reset(force=True, reset_portal_type=True)

    # TestPortalType must be in available type class list
    self.assertTrue('TestPortalType' in person_type.getDocumentTypeList())
    try:
      person_type.setTypeClass('TestPortalType')
      transaction.commit()

      self.assertHasAttribute(person, 'test42')
      self.assertEquals(person.test42(), 42)

      # The Portal Type class should not be in ghost state by now as we tried
      # to access test42() defined in TestPortalType Document Component
      self.assertModuleImportable('TestPortalType')
      self.assertTrue(self._module.TestPortalType.TestPortalType in person.__class__.mro())
      self.assertTrue(PersonDocument in person.__class__.mro())

    finally:
      person_type.setTypeClass('Person')
      transaction.commit()

  def testDocumentWithImport(self):
    self.failIfModuleImportable('TestDocumentWithImport')
    self.failIfModuleImportable('TestDocumentImported')

    # Create a new Document Component inheriting from Person Document which
    # defines only one additional method (meaningful to make sure that the
    # class (and not the module) has been added to the class when the
    # TypeClass is changed)
    test_imported_component = self._newComponent(
      'TestDocumentImported',
      """
from Products.ERP5Type.Document.Person import Person

class TestDocumentImported(Person):
  def test42(self):
    return 42
""")

    test_component = self._newComponent(
      'TestDocumentWithImport',
      """
from Products.ERP5.Document.Person import Person
from erp5.component.document.TestDocumentImported import TestDocumentImported

class TestDocumentWithImport(TestDocumentImported):
  def test42(self):
    return 4242
""")

    transaction.commit()
    self.tic()

    self.failIfModuleImportable('TestDocumentWithImport')
    self.failIfModuleImportable('TestDocumentImported')

    test_imported_component.validate()
    test_component.validate()
    transaction.commit()
    self.tic()

    # TestPortalWithImport must be imported first to check if
    # TestPortalImported could be imported without being present before
    self.assertModuleImportable('TestDocumentWithImport')
    self.assertModuleImportable('TestDocumentImported')

def test_suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.makeSuite(TestPortalTypeClass))
  suite.addTest(unittest.makeSuite(TestZodbPropertySheet))
  suite.addTest(unittest.makeSuite(TestZodbExtensionComponent))
  suite.addTest(unittest.makeSuite(TestZodbDocumentComponent))
  return suite
