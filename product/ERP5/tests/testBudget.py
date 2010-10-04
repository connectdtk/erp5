##############################################################################
#
# Copyright (c) 2005-2009 Nexedi SA and Contributors. All Rights Reserved.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
##############################################################################

import unittest

import transaction
from DateTime import DateTime

from Products.ERP5Type.tests.ERP5TypeTestCase import ERP5TypeTestCase
from AccessControl import getSecurityManager

class TestBudget(ERP5TypeTestCase):
  
  def afterSetUp(self):
    self.validateRules()
    product_line = self.portal.portal_categories.product_line
    if '1' not in product_line.objectIds():
      category = product_line.newContent(portal_type='Category', id='1')
      category.newContent(portal_type='Category', id='1.1')
      category.newContent(portal_type='Category', id='1.2')
    if '2' not in product_line.objectIds():
      category = product_line.newContent(portal_type='Category', id='2')
      category.newContent(portal_type='Category', id='2.1')
      category.newContent(portal_type='Category', id='2.2')

  def beforeTearDown(self):
    transaction.abort()
    self.portal.accounting_module.manage_delObjects(
       list(self.portal.accounting_module.objectIds()))
    transaction.commit()
    self.tic()

  def getBusinessTemplateList(self):
    """Return the list of required business templates.
    We'll use erp5_accounting_ui_test to have some content
    """
    return ('erp5_base', 'erp5_pdm', 'erp5_trade', 'erp5_accounting',
            'erp5_invoicing', 'erp5_simplified_invoicing',
            'erp5_accounting_ui_test', 'erp5_budget')

  # creation and basic functionalities
  def test_simple_create_budget_model(self):
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget_cell',
                    inventory_axis='node_category',
                    variation_base_category='site',
                    )
    self.assertEquals([], budget_model.checkConsistency())

  def test_simple_create_budget(self):
    budget = self.portal.budget_module.newContent(
                            portal_type='Budget')
    budget_line = budget.newContent(portal_type='Budget Line')
    budget_cell = budget_line.newContent(portal_type='Budget Cell')
    self.assertEquals([], budget.checkConsistency())

  def test_budget_cell_node_variation_with_aggregate(self):
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Node Budget Variation',
                    int_index=1,
                    budget_variation='budget_cell',
                    inventory_axis='node',
                    variation_base_category='source',
                    aggregate_value_list=(
                      self.portal.account_module.goods_purchase,
                      self.portal.account_module.fixed_assets,
                    ))
    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    specialise_value=budget_model)
    budget_line = budget.newContent(portal_type='Budget Line')
    self.assertEquals(['source'],
                      budget_line.getVariationBaseCategoryList())
    self.assertEquals(
        [('Goods Purchase', 'source/account_module/goods_purchase'),
         ('Fixed Assets', 'source/account_module/fixed_assets')],
        budget_line.BudgetLine_getVariationRangeCategoryList())

    budget_line.setVariationCategoryList(
         ('source/account_module/goods_purchase',))
    self.assertEquals(
        ['source/account_module/goods_purchase'],
        budget_line.getVariationCategoryList())
  
    # This was a budget cell variation, so no criterion is set on budget line
    self.assertEquals(budget_line.getMembershipCriterionCategoryList(), [])
    self.assertEquals(
        budget_line.getMembershipCriterionBaseCategoryList(), [])
    

    # simuate a request and call Base_edit, which does all the work of creating
    # cell and setting cell properties.
    form = budget_line.BudgetLine_view
    self.portal.REQUEST.other.update(
        dict(AUTHENTICATED_USER=getSecurityManager().getUser(),

             field_membership_criterion_base_category_list=
        form.membership_criterion_base_category_list.get_value('default'),
             field_mapped_value_property_list=
        form.mapped_value_property_list.get_value('default'),

             field_matrixbox_quantity_cell_0_0_0="5",
             field_matrixbox_membership_criterion_category_list_cell_0_0_0=[
               'source/account_module/goods_purchase'],
        ))
    budget_line.Base_edit(form_id=form.getId())

    self.assertEquals(1, len(budget_line.contentValues()))
    budget_cell = budget_line.getCell('source/account_module/goods_purchase')
    self.assertNotEquals(None, budget_cell)

    self.assertEquals(['source/account_module/goods_purchase'],
        budget_cell.getMembershipCriterionCategoryList())
    self.assertEquals(5, budget_cell.getQuantity())

    # there is no budget consumption
    self.assertEquals(0, budget_cell.getConsumedBudget())
    self.assertEquals(0, budget_cell.getEngagedBudget())
    self.assertEquals(5, budget_cell.getAvailableBudget())
    # there is no budget transfer
    self.assertEquals(5, budget_cell.getCurrentBalance())


  def test_category_budget_cell_variation(self):
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget_cell',
                    inventory_axis='node_category',
                    variation_base_category='account_type',)
    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    specialise_value=budget_model)
    budget_line = budget.newContent(portal_type='Budget Line')
    self.assertEquals(['account_type'],
                      budget_line.getVariationBaseCategoryList())

    variation_range_category_list = \
       budget_line.BudgetLine_getVariationRangeCategoryList()
    self.assertTrue(['', ''] in variation_range_category_list)
    self.assertTrue(['Expense', 'account_type/expense'] in variation_range_category_list)

  def test_category_budget_line_variation(self):
    # test that using a variation on budget line level sets membership
    # criterion on budget line
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget_line',
                    inventory_axis='section_category',
                    variation_base_category='group',)
    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    specialise_value=budget_model)
    budget_line = budget.newContent(portal_type='Budget Line')

    self.assertEquals(['group'],
                      budget_line.getVariationBaseCategoryList())

    variation_range_category_list = \
       budget_line.BudgetLine_getVariationRangeCategoryList()

    self.assertTrue(['', ''] in variation_range_category_list)
    self.assertTrue(['Demo Group', 'group/demo_group'] in variation_range_category_list)
    
    budget_line.edit(variation_category_list=['group/demo_group'])
    self.assertEquals(['group'],
        budget_line.getMembershipCriterionBaseCategoryList())
    self.assertEquals(['group/demo_group'],
        budget_line.getMembershipCriterionCategoryList())

  def test_category_budget_line_and_budget_cell_variation(self):
    # test that using a variation on budget line level sets membership
    # criterion on budget line, but not on budget cell
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget_line',
                    inventory_axis='section_category',
                    variation_base_category='group',)
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=2,
                    budget_variation='budget_cell',
                    inventory_axis='node_category',
                    variation_base_category='account_type',)
    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    specialise_value=budget_model)
    budget_line = budget.newContent(portal_type='Budget Line')

    self.assertEquals(['group', 'account_type'],
                      budget_line.getVariationBaseCategoryList())
    
    budget_line.edit(variation_category_list=['group/demo_group',
                                              'account_type/expense'])
    self.assertEquals(['group'],
        budget_line.getMembershipCriterionBaseCategoryList())
    self.assertEquals(['group/demo_group'],
        budget_line.getMembershipCriterionCategoryList())

    form = budget_line.BudgetLine_view
    self.portal.REQUEST.other.update(
        dict(AUTHENTICATED_USER=getSecurityManager().getUser(),

             field_membership_criterion_base_category_list=
        form.membership_criterion_base_category_list.get_value('default'),
             field_mapped_value_property_list=
        form.mapped_value_property_list.get_value('default'),

             field_matrixbox_quantity_cell_0_0_0="1",
             field_matrixbox_membership_criterion_category_list_cell_0_0_0=[
               'account_type/expense'],
        ))
    budget_line.Base_edit(form_id=form.getId())

    self.assertEquals(1, len(budget_line.contentValues()))
    budget_cell = budget_line.getCell('account_type/expense')
    self.assertEquals(['account_type'],
                       budget_cell.getMembershipCriterionBaseCategoryList())
    self.assertEquals(['account_type/expense'],
                       budget_cell.getMembershipCriterionCategoryList())


  def test_category_budget_variation(self):
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget',
                    inventory_axis='section_category',
                    variation_base_category='group',)
    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    specialise_value=budget_model)

    self.assertEquals(['group'],
                      budget.getVariationBaseCategoryList())

    variation_range_category_list = \
       budget.Budget_getVariationRangeCategoryList()

    self.assertTrue(['', ''] in variation_range_category_list)
    self.assertTrue(['Demo Group', 'group/demo_group'] in variation_range_category_list)

    # setting this variation on the budget also sets membership
    budget.edit(variation_category_list=['group/demo_group'])
    self.assertEquals('demo_group', budget.getGroup())
    self.assertEquals('Demo Group', budget.getGroupTitle())

  # consumptions
  def test_simple_consumption(self):
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget',
                    inventory_axis='section_category',
                    variation_base_category='group',)
    budget_model.newContent(
                    portal_type='Node Budget Variation',
                    int_index=2,
                    budget_variation='budget_cell',
                    inventory_axis='node',
                    variation_base_category='source',
                    aggregate_value_list=(
                      self.portal.account_module.goods_purchase,
                      self.portal.account_module.fixed_assets,
                    ))
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=3,
                    budget_variation='budget_cell',
                    inventory_axis='node_category',
                    variation_base_category='account_type',)

    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    start_date_range_min=DateTime(2000, 1, 1),
                    start_date_range_max=DateTime(2000, 12, 31),
                    specialise_value=budget_model)

    budget.edit(variation_category_list=['group/demo_group'])
    budget_line = budget.newContent(portal_type='Budget Line')

    # set the range, this will adjust the matrix
    budget_line.edit(
        variation_category_list=(
          'source/account_module/goods_purchase',
          'source/account_module/fixed_assets',
          'account_type/expense',
          'account_type/asset', ))

    # simuate a request and call Base_edit, which does all the work of creating
    # cell and setting cell properties.
    form = budget_line.BudgetLine_view
    self.portal.REQUEST.other.update(
        dict(AUTHENTICATED_USER=getSecurityManager().getUser(),

             field_membership_criterion_base_category_list=
        form.membership_criterion_base_category_list.get_value('default'),
             field_mapped_value_property_list=
        form.mapped_value_property_list.get_value('default'),

             field_matrixbox_quantity_cell_0_0_0="",
             field_matrixbox_membership_criterion_category_list_cell_0_0_0=[],
             field_matrixbox_quantity_cell_1_0_0="2",
             field_matrixbox_membership_criterion_category_list_cell_1_0_0=[
               'source/account_module/fixed_assets',
               'account_type/asset'],
             field_matrixbox_quantity_cell_0_1_0="1",
             field_matrixbox_membership_criterion_category_list_cell_0_1_0=[
               'source/account_module/goods_purchase',
               'account_type/expense'],
             field_matrixbox_quantity_cell_1_1_0="",
             field_matrixbox_membership_criterion_category_list_cell_1_1_0=[],
        ))
    budget_line.Base_edit(form_id=form.getId())

    self.assertEquals(2, len(budget_line.contentValues()))
    budget_cell = budget_line.getCell('source/account_module/goods_purchase',
                                      'account_type/expense')
    self.assertNotEquals(None, budget_cell)
    self.assertEquals(
        dict(from_date=DateTime(2000, 1, 1),
             at_date=DateTime(2000, 12, 31).latestTime(),
             node_category=['account_type/expense'],
             node_uid=[self.portal.account_module.goods_purchase.getUid()],
             section_category=['group/demo_group'],),
        budget_model.getInventoryQueryDict(budget_cell))

    budget_cell = budget_line.getCell('source/account_module/fixed_assets',
                                      'account_type/asset')
    self.assertNotEquals(None, budget_cell)
    self.assertEquals(
        dict(from_date=DateTime(2000, 1, 1),
             at_date=DateTime(2000, 12, 31).latestTime(),
             node_category=['account_type/asset'],
             node_uid=[self.portal.account_module.fixed_assets.getUid()],
             section_category=['group/demo_group'],),
        budget_model.getInventoryQueryDict(budget_cell))

    self.assertEquals(
        dict(from_date=DateTime(2000, 1, 1),
             at_date=DateTime(2000, 12, 31).latestTime(),
             node_category=['account_type/expense', 'account_type/asset'],
             node_uid=[self.portal.account_module.goods_purchase.getUid(),
                       self.portal.account_module.fixed_assets.getUid()],
             section_category=['group/demo_group'],
             group_by_node_category=True,
             group_by_node=True,
             group_by_section_category=True,
             ),
        budget_model.getInventoryListQueryDict(budget_line))


    atransaction = self.portal.accounting_module.newContent(
                  portal_type='Accounting Transaction',
                  resource_value=self.portal.currency_module.euro,
                  source_section_value=self.portal.organisation_module.my_organisation,
                  start_date=DateTime(2000, 1, 2))
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.goods_purchase,
                  source_debit=100)
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.fixed_assets,
                  source_credit=100)
    atransaction.stop()

    transaction.commit()
    self.tic()

    self.assertEquals(
      {('source/account_module/fixed_assets', 'account_type/asset'): -100.0,
       ('source/account_module/goods_purchase', 'account_type/expense'): 100.0},
        budget_line.getConsumedBudgetDict())

    self.assertEquals(
      {('source/account_module/fixed_assets', 'account_type/asset'): -100.0,
       ('source/account_module/goods_purchase', 'account_type/expense'): 100.0},
        budget_line.getEngagedBudgetDict())

    self.assertEquals(
      {('source/account_module/fixed_assets', 'account_type/asset'): 102.0,
       ('source/account_module/goods_purchase', 'account_type/expense'): -99.0},
        budget_line.getAvailableBudgetDict())
      
    # we can view the forms without error
    budget_line.BudgetLine_viewEngagedBudget()
    budget_line.BudgetLine_viewConsumedBudget()
    budget_line.BudgetLine_viewAvailableBudget()

  def test_all_other_and_strict_consumption(self):
    # tests consumptions, by using "all other" virtual node on a node budget
    # variation, and strict membership on category budget variation
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget',
                    inventory_axis='section_category_strict_membership',
                    variation_base_category='group',)
    budget_model.newContent(
                    portal_type='Node Budget Variation',
                    int_index=2,
                    budget_variation='budget_cell',
                    inventory_axis='node',
                    variation_base_category='source',
                    aggregate_value_list=(
                      self.portal.account_module.goods_purchase,),
                    include_virtual_other_node=True)
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=3,
                    budget_variation='budget_cell',
                    inventory_axis='node_category_strict_membership',
                    variation_base_category='account_type',)

    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    start_date_range_min=DateTime(2000, 1, 1),
                    start_date_range_max=DateTime(2000, 12, 31),
                    specialise_value=budget_model)

    budget.edit(variation_category_list=['group/demo_group/sub1'])
    budget_line = budget.newContent(portal_type='Budget Line')

    # set the range, this will adjust the matrix
    budget_line.edit(
        variation_category_list=(
          'source/account_module/goods_purchase',
          'source/%s' % budget_line.getRelativeUrl(), # this is 'all others'
          'account_type/expense',
          'account_type/asset', ))

    # simuate a request and call Base_edit, which does all the work of creating
    # cell and setting cell properties.
    form = budget_line.BudgetLine_view
    self.portal.REQUEST.other.update(
        dict(AUTHENTICATED_USER=getSecurityManager().getUser(),

             field_membership_criterion_base_category_list=
        form.membership_criterion_base_category_list.get_value('default'),
             field_mapped_value_property_list=
        form.mapped_value_property_list.get_value('default'),

             field_matrixbox_quantity_cell_0_0_0="",
             field_matrixbox_membership_criterion_category_list_cell_0_0_0=[],
             field_matrixbox_quantity_cell_1_0_0="2",
             field_matrixbox_membership_criterion_category_list_cell_1_0_0=[
               'source/%s' % budget_line.getRelativeUrl(),
               'account_type/asset'],
             field_matrixbox_quantity_cell_0_1_0="1",
             field_matrixbox_membership_criterion_category_list_cell_0_1_0=[
               'source/account_module/goods_purchase',
               'account_type/expense'],
             field_matrixbox_quantity_cell_1_1_0="",
             field_matrixbox_membership_criterion_category_list_cell_1_1_0=[],
        ))
    budget_line.Base_edit(form_id=form.getId())

    self.assertEquals(2, len(budget_line.contentValues()))

    self.assertEquals(
        dict(from_date=DateTime(2000, 1, 1),
             at_date=DateTime(2000, 12, 31).latestTime(),
             node_category_strict_membership=['account_type/expense',
                                              'account_type/asset'],
             section_category_strict_membership=['group/demo_group/sub1'],
             group_by_node_category_strict_membership=True,
             group_by_node=True,
             group_by_section_category_strict_membership=True,
             ),
        budget_model.getInventoryListQueryDict(budget_line))


    atransaction = self.portal.accounting_module.newContent(
                  portal_type='Accounting Transaction',
                  resource_value=self.portal.currency_module.euro,
                  source_section_value=self.portal.organisation_module.my_organisation,
                  start_date=DateTime(2000, 1, 2))
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.goods_purchase,
                  source_debit=100)
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.fixed_assets,
                  source_credit=100)
    atransaction.stop()

    transaction.commit()
    self.tic()

    self.assertEquals(
      {('source/%s' % budget_line.getRelativeUrl(), 'account_type/asset'): -100.0,
       ('source/account_module/goods_purchase', 'account_type/expense'): 100.0},
        budget_line.getConsumedBudgetDict())

    self.assertEquals(
      {('source/%s' % budget_line.getRelativeUrl(), 'account_type/asset'): -100.0,
       ('source/account_module/goods_purchase', 'account_type/expense'): 100.0},
        budget_line.getEngagedBudgetDict())

    self.assertEquals(
      {('source/%s' % budget_line.getRelativeUrl(), 'account_type/asset'): 102.0,
       ('source/account_module/goods_purchase', 'account_type/expense'): -99.0},
        budget_line.getAvailableBudgetDict())
      

  def test_consumption_movement_category(self):
    # test for budget consumption using movement category
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget',
                    inventory_axis='section_category',
                    variation_base_category='group',)
    budget_model.newContent(
                    portal_type='Node Budget Variation',
                    int_index=2,
                    budget_variation='budget_cell',
                    inventory_axis='node',
                    variation_base_category='source',
                    aggregate_value_list=(
                      self.portal.account_module.goods_purchase,
                      self.portal.account_module.fixed_assets,
                    ))
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=3,
                    budget_variation='budget_cell',
                    inventory_axis='movement',
                    variation_base_category='product_line',)

    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    start_date_range_min=DateTime(2000, 1, 1),
                    start_date_range_max=DateTime(2000, 12, 31),
                    specialise_value=budget_model)

    budget.edit(variation_category_list=['group/demo_group'])
    budget_line = budget.newContent(portal_type='Budget Line')

    # set the range, this will adjust the matrix
    budget_line.edit(
        variation_category_list=(
          'source/account_module/goods_purchase',
          'source/account_module/fixed_assets',
          'product_line/1',
          'product_line/1/1.1',
          'product_line/1/1.2', ))

    # simuate a request and call Base_edit, which does all the work of creating
    # cell and setting cell properties.
    form = budget_line.BudgetLine_view
    self.portal.REQUEST.other.update(
        dict(AUTHENTICATED_USER=getSecurityManager().getUser(),

             field_membership_criterion_base_category_list=
        form.membership_criterion_base_category_list.get_value('default'),
             field_mapped_value_property_list=
        form.mapped_value_property_list.get_value('default'),

            # this cell will be a summary cell
             field_matrixbox_quantity_cell_0_0_0="2",
             field_matrixbox_membership_criterion_category_list_cell_0_0_0=[
               'source/account_module/goods_purchase',
               'product_line/1'],
             field_matrixbox_quantity_cell_1_0_0="",
             field_matrixbox_membership_criterion_category_list_cell_1_0_0=[],
             field_matrixbox_quantity_cell_0_1_0="2",
             field_matrixbox_membership_criterion_category_list_cell_0_1_0=[
               'source/account_module/goods_purchase',
               'product_line/1/1.1'],
             field_matrixbox_quantity_cell_1_1_0="",
             field_matrixbox_membership_criterion_category_list_cell_1_1_0=[],
             field_matrixbox_quantity_cell_0_2_0="",
             field_matrixbox_membership_criterion_category_list_cell_0_2_0=[],
             field_matrixbox_quantity_cell_1_2_0="",
             field_matrixbox_membership_criterion_category_list_cell_1_2_0=[],
        ))
    budget_line.Base_edit(form_id=form.getId())

    self.assertEquals(2, len(budget_line.contentValues()))

    product_line_1 = self.portal.portal_categories.product_line['1']
    product_line_1_11 = product_line_1['1.1']
    product_line_1_12 = product_line_1['1.2']

    self.assertEquals(
        dict(from_date=DateTime(2000, 1, 1),
             at_date=DateTime(2000, 12, 31).latestTime(),
             node_uid=[self.portal.account_module.goods_purchase.getUid(),
                       self.portal.account_module.fixed_assets.getUid(),],
             default_product_line_uid=[product_line_1.getUid(),
                                       product_line_1_11.getUid(),
                                       product_line_1_12.getUid(),],
             section_category=['group/demo_group'],
             group_by=['default_product_line_uid'],
             # select list is passed, because getInventoryList does not add
             # group by related keys to select
             select_list=['default_product_line_uid'],
             group_by_node=True,
             group_by_section_category=True,
             ),
        budget_model.getInventoryListQueryDict(budget_line))


    atransaction = self.portal.accounting_module.newContent(
                  portal_type='Accounting Transaction',
                  resource_value=self.portal.currency_module.euro,
                  source_section_value=self.portal.organisation_module.my_organisation,
                  start_date=DateTime(2000, 1, 2))
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.goods_purchase,
                  product_line_value=product_line_1_11,
                  source_debit=100)
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.fixed_assets,
                  product_line_value=product_line_1_12,
                  source_credit=100)
    atransaction.stop()

    transaction.commit()
    self.tic()

    self.assertEquals(
      {('source/account_module/fixed_assets', 'product_line/1/1.2'): -100.0,
       ('source/account_module/goods_purchase', 'product_line/1/1.1'): 100.0,
       # summary lines are automatically added
       ('source/account_module/fixed_assets', 'product_line/1'): -100.0,
       ('source/account_module/goods_purchase', 'product_line/1'): 100.0
       },
        budget_line.getConsumedBudgetDict())

    self.assertEquals(
      {('source/account_module/fixed_assets', 'product_line/1/1.2'): -100.0,
       ('source/account_module/goods_purchase', 'product_line/1/1.1'): 100.0,
       ('source/account_module/fixed_assets', 'product_line/1'): -100.0,
       ('source/account_module/goods_purchase', 'product_line/1'): 100.0
       },
        budget_line.getEngagedBudgetDict())

    self.assertEquals(
      {('source/account_module/fixed_assets', 'product_line/1/1.2'): 100.0,
       ('source/account_module/goods_purchase', 'product_line/1/1.1'): -98.0,
       ('source/account_module/fixed_assets', 'product_line/1'): 100.0,
       ('source/account_module/goods_purchase', 'product_line/1'): -98,
       },
        budget_line.getAvailableBudgetDict())

  def test_consumption_category_variation_summary(self):
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget_cell',
                    inventory_axis='section_category',
                    variation_base_category='group',)
    budget_model.newContent(
                    portal_type='Node Budget Variation',
                    int_index=2,
                    budget_variation='budget_cell',
                    inventory_axis='node',
                    variation_base_category='source',
                    aggregate_value_list=(
                      self.portal.account_module.goods_purchase,
                      self.portal.account_module.fixed_assets,
                    ))
    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    start_date_range_min=DateTime(2000, 1, 1),
                    start_date_range_max=DateTime(2000, 12, 31),
                    specialise_value=budget_model)

    budget_line = budget.newContent(portal_type='Budget Line',)

    # set the range, this will adjust the matrix
    budget_line.edit(
        variation_category_list=(
          'source/account_module/goods_purchase',
          'group/demo_group',
          'group/demo_group/sub1',
          ))
    
    form = budget_line.BudgetLine_view
    self.portal.REQUEST.other.update(
        dict(AUTHENTICATED_USER=getSecurityManager().getUser(),

             field_membership_criterion_base_category_list=
        form.membership_criterion_base_category_list.get_value('default'),
             field_mapped_value_property_list=
        form.mapped_value_property_list.get_value('default'),

             field_matrixbox_quantity_cell_0_0_0="",
             field_matrixbox_membership_criterion_category_list_cell_0_0_0=[],
             field_matrixbox_quantity_cell_1_0_0="500",
             field_matrixbox_membership_criterion_category_list_cell_1_0_0=[
               'group/demo_group/sub1',
               'source/account_module/goods_purchase', ],
        ))
    budget_line.Base_edit(form_id=form.getId())

    self.assertEquals(1, len(budget_line.contentValues()))

    self.assertEquals(
        dict(from_date=DateTime(2000, 1, 1),
             at_date=DateTime(2000, 12, 31).latestTime(),
             node_uid=[self.portal.account_module.goods_purchase.getUid(),],
             section_category=['group/demo_group',
                               'group/demo_group/sub1'],
             group_by_node=True,
             group_by_section_category=True,
             ),
        budget_model.getInventoryListQueryDict(budget_line))


    atransaction = self.portal.accounting_module.newContent(
                  portal_type='Accounting Transaction',
                  resource_value=self.portal.currency_module.euro,
                  source_section_value=self.portal.organisation_module.my_organisation,
                  start_date=DateTime(2000, 1, 2))
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.goods_purchase,
                  source_debit=100)
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.fixed_assets,
                  source_credit=100)
    atransaction.stop()

    transaction.commit()
    self.tic()

    self.assertEquals(
      {('group/demo_group/sub1', 'source/account_module/goods_purchase'): 100.0,
       ('group/demo_group', 'source/account_module/goods_purchase'): 100.0,},
       budget_line.getConsumedBudgetDict())

    self.assertEquals(
      {('group/demo_group/sub1', 'source/account_module/goods_purchase'): 100.0,
       ('group/demo_group', 'source/account_module/goods_purchase'): 100.0,},
       budget_line.getEngagedBudgetDict())

  def test_consumption_node_budget_variation_not_set(self):
    # test consumption calculation when a node budget variation is used, but
    # this variation category is not set
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget_cell',
                    inventory_axis='section_category',
                    variation_base_category='group',)
    budget_model.newContent(
                    portal_type='Node Budget Variation',
                    int_index=2,
                    budget_variation='budget_cell',
                    inventory_axis='node',
                    variation_base_category='source',
                    aggregate_value_list=(
                      self.portal.account_module.goods_purchase,
                      self.portal.account_module.fixed_assets,
                    ))
    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    start_date_range_min=DateTime(2000, 1, 1),
                    start_date_range_max=DateTime(2000, 12, 31),
                    specialise_value=budget_model)

    budget_line = budget.newContent(portal_type='Budget Line',)

    # we don't set 
    budget_line.edit(
        variation_category_list=(
          'group/demo_group/sub1',
          ))
    
    form = budget_line.BudgetLine_view
    self.portal.REQUEST.other.update(
        dict(AUTHENTICATED_USER=getSecurityManager().getUser(),

             field_membership_criterion_base_category_list=
        form.membership_criterion_base_category_list.get_value('default'),
             field_mapped_value_property_list=
        form.mapped_value_property_list.get_value('default'),

             field_matrixbox_quantity_cell_0_0_0="500",
             field_matrixbox_membership_criterion_category_list_cell_0_0_0=[
               'group/demo_group/sub1', ],
        ))
    budget_line.Base_edit(form_id=form.getId())

    self.assertEquals(1, len(budget_line.contentValues()))

    self.assertEquals(
        dict(from_date=DateTime(2000, 1, 1),
             at_date=DateTime(2000, 12, 31).latestTime(),
             section_category=['group/demo_group/sub1',],
             group_by_section_category=True,
             ),
        budget_model.getInventoryListQueryDict(budget_line))


    atransaction = self.portal.accounting_module.newContent(
                  portal_type='Accounting Transaction',
                  resource_value=self.portal.currency_module.euro,
                  source_section_value=self.portal.organisation_module.my_organisation,
                  start_date=DateTime(2000, 1, 2))
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.goods_purchase,
                  source_debit=100)
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.fixed_assets,
                  source_credit=100)
    atransaction.stop()

    transaction.commit()
    self.tic()

    self.assertEquals(
      {('group/demo_group/sub1', ): 0.0, },
       budget_line.getConsumedBudgetDict())

    self.assertEquals(
      {('group/demo_group/sub1', ): 0.0, },
       budget_line.getEngagedBudgetDict())

  def test_consumption_category_budget_variation_not_set(self):
    # test consumption calculation when a category budget variation is used, but
    # this variation category is not set
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget_cell',
                    inventory_axis='section_category',
                    variation_base_category='group',)
    budget_model.newContent(
                    portal_type='Node Budget Variation',
                    int_index=2,
                    budget_variation='budget_cell',
                    inventory_axis='node',
                    variation_base_category='source',
                    aggregate_value_list=(
                      self.portal.account_module.goods_purchase,
                      self.portal.account_module.fixed_assets,
                    ))
    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    start_date_range_min=DateTime(2000, 1, 1),
                    start_date_range_max=DateTime(2000, 12, 31),
                    specialise_value=budget_model)

    budget_line = budget.newContent(portal_type='Budget Line',)

    # we don't set 
    budget_line.edit(
        variation_category_list=(
          'source/account_module/goods_purchase',
          ))
    
    form = budget_line.BudgetLine_view
    self.portal.REQUEST.other.update(
        dict(AUTHENTICATED_USER=getSecurityManager().getUser(),

             field_membership_criterion_base_category_list=
        form.membership_criterion_base_category_list.get_value('default'),
             field_mapped_value_property_list=
        form.mapped_value_property_list.get_value('default'),

             field_matrixbox_quantity_cell_0_0_0="500",
             field_matrixbox_membership_criterion_category_list_cell_0_0_0=[
               'source/account_module/goods_purchase', ],
        ))
    budget_line.Base_edit(form_id=form.getId())

    self.assertEquals(1, len(budget_line.contentValues()))

    self.assertEquals(
        dict(from_date=DateTime(2000, 1, 1),
             at_date=DateTime(2000, 12, 31).latestTime(),
             node_uid=[self.portal.account_module.goods_purchase.getUid(),],
             group_by_node=True,
             ),
        budget_model.getInventoryListQueryDict(budget_line))


    atransaction = self.portal.accounting_module.newContent(
                  portal_type='Accounting Transaction',
                  resource_value=self.portal.currency_module.euro,
                  source_section_value=self.portal.organisation_module.my_organisation,
                  start_date=DateTime(2000, 1, 2))
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.goods_purchase,
                  source_debit=100)
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.fixed_assets,
                  source_credit=100)
    atransaction.stop()

    transaction.commit()
    self.tic()

    self.assertEquals(
      {('source/account_module/goods_purchase', ): 100.0, },
       budget_line.getConsumedBudgetDict())

    self.assertEquals(
      {('source/account_module/goods_purchase', ): 100.0, },
       budget_line.getEngagedBudgetDict())

  def test_multiple_variation_line_level(self):
    # tests the behaviour of getInventoryListQueryDict and
    # getInventoryQueryDict when we are using budget line level variation with
    # multiple variation set. It should be a 'OR' between all the selected
    # variations.
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Node Budget Variation',
                    int_index=1,
                    budget_variation='budget_line',
                    inventory_axis='node',
                    variation_base_category='source',
                    aggregate_value_list=(
                      self.portal.account_module.goods_purchase,
                      self.portal.account_module.fixed_assets,
                    ))
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=2,
                    budget_variation='budget_line',
                    inventory_axis='section_category',
                    variation_base_category='group',)
    # this variation will be needed to create cells
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=3,
                    budget_variation='budget_cell',
                    inventory_axis='node_category_strict_membership',
                    variation_base_category='account_type',)

    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    specialise_value=budget_model)
    budget_line = budget.newContent(portal_type='Budget Line')

    budget_line.edit(
        variation_category_list=['group/demo_group/sub1',
                                 'group/demo_group/sub2',
                                 'source/account_module/goods_purchase',
                                 'source/account_module/fixed_assets',
                                 ])
    self.assertEquals({
      'from_date': None,
      'group_by_node': True,
      'group_by_section_category': True,
      'section_category': ['group/demo_group/sub1',
                           'group/demo_group/sub2'],
      'node_uid': [self.portal.account_module.goods_purchase.getUid(),
                   self.portal.account_module.fixed_assets.getUid()], },
      budget_model.getInventoryListQueryDict(budget_line))

    self.assertEquals({
      'from_date': None,
      'simulation_state': ('delivered', 'stopped'),
      # XXX order is reversed for some reason ...
      'section_category': ['group/demo_group/sub2',
                           'group/demo_group/sub1'],
      'node_uid': [self.portal.account_module.fixed_assets.getUid(),
                   self.portal.account_module.goods_purchase.getUid()],
      'node_category_strict_membership': ['account_type/expense']},

      # BudgetLine_getInventoryQueryDictForCellIndex uses getInventoryQueryDict
      # but does not require the cell to be physically present
      budget_line.BudgetLine_getInventoryQueryDictForCellIndex(
        cell_index=('account_type/expense')))

  
  # Report
  def test_budget_consumption_report(self):
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget',
                    inventory_axis='section_category',
                    variation_base_category='group',)
    budget_model.newContent(
                    portal_type='Node Budget Variation',
                    int_index=2,
                    budget_variation='budget_cell',
                    inventory_axis='node',
                    variation_base_category='source',
                    aggregate_value_list=(
                      self.portal.account_module.goods_purchase,
                      self.portal.account_module.fixed_assets,
                    ))
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=3,
                    budget_variation='budget_cell',
                    inventory_axis='node_category',
                    variation_base_category='account_type',)

    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    title='Budget Title',
                    start_date_range_min=DateTime(2000, 1, 1),
                    start_date_range_max=DateTime(2000, 12, 31),
                    specialise_value=budget_model)

    budget.edit(variation_category_list=['group/demo_group'])
    budget_line = budget.newContent(portal_type='Budget Line',
                                    title='Budget Line Title',)

    # set the range, this will adjust the matrix
    budget_line.edit(
        variation_category_list=(
          'source/account_module/goods_purchase',
          'source/account_module/fixed_assets',
          'account_type/asset', ))

    # simuate a request and call Base_edit, which does all the work of creating
    # cell and setting cell properties.
    form = budget_line.BudgetLine_view
    self.portal.REQUEST.other.update(
        dict(AUTHENTICATED_USER=getSecurityManager().getUser(),

             field_membership_criterion_base_category_list=
        form.membership_criterion_base_category_list.get_value('default'),
             field_mapped_value_property_list=
        form.mapped_value_property_list.get_value('default'),

             field_matrixbox_quantity_cell_0_0_0="",
             field_matrixbox_membership_criterion_category_list_cell_0_0_0=[],
             field_matrixbox_quantity_cell_1_0_0="200",
             field_matrixbox_membership_criterion_category_list_cell_1_0_0=[
               'source/account_module/fixed_assets',
               'account_type/asset'],
        ))
    budget_line.Base_edit(form_id=form.getId())

    atransaction = self.portal.accounting_module.newContent(
                  portal_type='Accounting Transaction',
                  resource_value=self.portal.currency_module.euro,
                  source_section_value=self.portal.organisation_module.my_organisation,
                  start_date=DateTime(2000, 1, 2))
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.goods_purchase,
                  source_credit=100)
    atransaction.newContent(
                  portal_type='Accounting Transaction Line',
                  source_value=self.portal.account_module.fixed_assets,
                  source_debit=100)
    atransaction.stop()

    transaction.commit()
    self.tic()
   
    # Budget_getBudgetConsumptionReportData returns all the data for the report
    line_list, line_count = budget.Budget_getBudgetConsumptionReportData()
    # the number of lines, which will be used in the report to set the print
    # range
    self.assertEquals(6, line_count)
    # number of line can be different from the length of the line list, because
    # line list is a recursive structure.
    self.assertEquals(4, len(line_list))
    
    # first line is for the title of the budget
    self.assertEquals('Budget Title', line_list[0]['title'])
    self.assertTrue(line_list[0]['is_budget'])
    
    # then we have a first level for budget lines
    self.assertEquals('Budget Line Title', line_list[1]['title'])
    self.assertTrue(line_list[1]['is_level_1'])
    # we can see global consumptions for the budget
    self.assertEquals(200, line_list[2]['initial_budget'])
    self.assertEquals(200, line_list[2]['current_budget'])
    self.assertEquals(100, line_list[2]['consumed_budget'])
    self.assertEquals(100, line_list[2]['engaged_budget'])
    self.assertEquals(.5, line_list[2]['consumed_ratio'])
    
    # the dimensions are reversed in the budget report, so on level 2 we have
    # the last dimension from cell range, here "account type"
    self.assertEquals('Asset', line_list[2]['title'])
    # we can see global consumptions for that summary line
    self.assertEquals(200, line_list[2]['initial_budget'])
    self.assertEquals(200, line_list[2]['current_budget'])
    self.assertEquals(100, line_list[2]['consumed_budget'])
    self.assertEquals(100, line_list[2]['engaged_budget'])
    self.assertEquals(.5, line_list[2]['consumed_ratio'])

    # no we have a recursive list, for the next dimension: node.
    self.assertTrue(isinstance(line_list[3], list))
    self.assertEquals(3, len(line_list[3]))

    # first is again a title XXX why ??
    self.assertEquals('Asset', line_list[3][0]['title'])
    # then we have two level 3 cells
    self.assertTrue(line_list[3][1]['is_level_3'])
    self.assertEquals('Goods Purchase', line_list[3][1]['title'])
    self.assertEquals(0, line_list[3][1]['initial_budget'])
    self.assertEquals(0, line_list[3][1]['current_budget'])
    self.assertEquals(0, line_list[3][1]['consumed_budget'])
    self.assertEquals(0, line_list[3][1]['engaged_budget'])
    self.assertEquals(0, line_list[3][1]['consumed_ratio'])

    self.assertEquals('Fixed Assets', line_list[3][2]['title'])
    self.assertEquals(200, line_list[3][2]['initial_budget'])
    self.assertEquals(200, line_list[3][2]['current_budget'])
    self.assertEquals(100, line_list[3][2]['consumed_budget'])
    self.assertEquals(100, line_list[3][2]['engaged_budget'])
    self.assertEquals(.5, line_list[3][2]['consumed_ratio'])

    # validate report ODF
    from Products.ERP5OOo.tests.utils import Validator
    odf_validator = Validator()
    odf = budget.Budget_viewBudgetConsumptionReport()
    err_list = odf_validator.validate(odf)
    if err_list:
      self.fail(''.join(err_list))

  # "update summary cells" feature
  def test_update_summary_cell_simple(self):
    # test the action to create or update quantity on summary cells
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget_cell',
                    inventory_axis='movement',
                    variation_base_category='product_line',)
    budget_model.newContent(
                    portal_type='Node Budget Variation',
                    int_index=2,
                    budget_variation='budget_cell',
                    inventory_axis='node',
                    variation_base_category='source',
                    aggregate_value_list=(
                      self.portal.account_module.goods_purchase,
                      self.portal.account_module.fixed_assets,
                    ))
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=3,
                    budget_variation='budget_cell',
                    inventory_axis='section_category',
                    variation_base_category='group',)

    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    start_date_range_min=DateTime(2000, 1, 1),
                    start_date_range_max=DateTime(2000, 12, 31),
                    specialise_value=budget_model)

    budget_line = budget.newContent(portal_type='Budget Line')

    # set the range, this will adjust the matrix
    budget_line.edit(
        variation_category_list=(
          'group/demo_group',
          'group/demo_group/sub1',
          'group/demo_group/sub2',
          'source/account_module/goods_purchase',
          'source/account_module/fixed_assets',
          'product_line/1',
          'product_line/1/1.1',
          'product_line/1/1.2', ))

    form = budget_line.BudgetLine_view
    self.portal.REQUEST.other.update(
        dict(AUTHENTICATED_USER=getSecurityManager().getUser(),

             field_membership_criterion_base_category_list=
        form.membership_criterion_base_category_list.get_value('default'),
             field_mapped_value_property_list=
        form.mapped_value_property_list.get_value('default'),
            
             # group/demo_group
             field_matrixbox_quantity_cell_0_0_0="",
             field_matrixbox_membership_criterion_category_list_cell_0_0_0=[],
             field_matrixbox_quantity_cell_1_0_0="",
             field_matrixbox_membership_criterion_category_list_cell_1_0_0=[],
             field_matrixbox_quantity_cell_2_0_0="",
             field_matrixbox_membership_criterion_category_list_cell_2_0_0=[],
             field_matrixbox_quantity_cell_0_1_0="",
             field_matrixbox_membership_criterion_category_list_cell_0_1_0=[],
             field_matrixbox_quantity_cell_1_1_0="",
             field_matrixbox_membership_criterion_category_list_cell_1_1_0=[],
             # This is a summary cell, but we set a manual value.
             field_matrixbox_quantity_cell_2_1_0="100",
             field_matrixbox_membership_criterion_category_list_cell_2_1_0=[
                'product_line/1/1.2',
                'source/account_module/fixed_assets',
                'group/demo_group',
                ],

             # group/demo_group/sub1
             field_matrixbox_quantity_cell_0_0_1="",
             field_matrixbox_membership_criterion_category_list_cell_0_0_1=[],
             field_matrixbox_quantity_cell_1_0_1="1",
             field_matrixbox_membership_criterion_category_list_cell_1_0_1=[
                'product_line/1/1.1',
                'source/account_module/goods_purchase',
                'group/demo_group/sub1',
                ],
             field_matrixbox_quantity_cell_2_0_1="2",
             field_matrixbox_membership_criterion_category_list_cell_2_0_1=[
                'product_line/1/1.2',
                'source/account_module/goods_purchase',
                'group/demo_group/sub1',
                ],
             field_matrixbox_quantity_cell_0_1_1="",
             field_matrixbox_membership_criterion_category_list_cell_0_1_1=[],
             field_matrixbox_quantity_cell_1_1_1="3",
             field_matrixbox_membership_criterion_category_list_cell_1_1_1=[
                'product_line/1/1.1',
                'source/account_module/fixed_assets',
                'group/demo_group/sub1',
               ],
             field_matrixbox_quantity_cell_2_1_1="4",
             field_matrixbox_membership_criterion_category_list_cell_2_1_1=[
                'product_line/1/1.2',
                'source/account_module/fixed_assets',
                'group/demo_group/sub1',
               ],

             # group/demo_group/sub2
             field_matrixbox_quantity_cell_0_0_2="",
             field_matrixbox_membership_criterion_category_list_cell_0_0_2=[],
             # we only have 1 cell here
             field_matrixbox_quantity_cell_1_0_2="5",
             field_matrixbox_membership_criterion_category_list_cell_1_0_2=[
                  'product_line/1/1.1',
                  'source/account_module/goods_purchase',
                  'group/demo_group/sub2',
                 ],
             field_matrixbox_quantity_cell_2_0_2="",
             field_matrixbox_membership_criterion_category_list_cell_2_0_2=[],
             # we have no cells here
             field_matrixbox_quantity_cell_0_1_2="",
             field_matrixbox_membership_criterion_category_list_cell_0_1_2=[],
             field_matrixbox_quantity_cell_1_1_2="",
             field_matrixbox_membership_criterion_category_list_cell_1_1_2=[],
             field_matrixbox_quantity_cell_2_1_2="",
             field_matrixbox_membership_criterion_category_list_cell_2_1_2=[],
        ))

    budget_line.Base_edit(form_id=form.getId())

    self.assertEquals(6, len(budget_line.contentValues()))

    budget_line.BudgetLine_setQuantityOnSummaryCellList()

    # summary cells have been created:
    self.assertEquals(14, len(budget_line.contentValues()))

    # those cells are aggregating
    self.assertEquals(1+2, budget_line.getCell(
                              'product_line/1',
                              'source/account_module/goods_purchase',
                              'group/demo_group/sub1',).getQuantity())
    self.assertEquals(4+3, budget_line.getCell(
                              'product_line/1',
                              'source/account_module/fixed_assets',
                              'group/demo_group/sub1',).getQuantity())
    self.assertEquals(1+5, budget_line.getCell(
                              'product_line/1/1.1',
                              'source/account_module/goods_purchase',
                              'group/demo_group',).getQuantity())
    self.assertEquals(1+2+5, budget_line.getCell(
                              'product_line/1',
                              'source/account_module/goods_purchase',
                              'group/demo_group',).getQuantity())

    # the cell that we have modified is erased
    self.assertEquals(4, budget_line.getCell(
                              'product_line/1/1.2',
                              'source/account_module/fixed_assets',
                              'group/demo_group',).getQuantity())

    # test all cells for complete coverage
    self.assertEquals(6, budget_line.getCell(
                              'product_line/1/1.1',
                              'source/account_module/goods_purchase',
                              'group/demo_group',).getQuantity())
    self.assertEquals(2, budget_line.getCell(
                              'product_line/1/1.2',
                              'source/account_module/goods_purchase',
                              'group/demo_group',).getQuantity())
    self.assertEquals(3+4, budget_line.getCell(
                              'product_line/1',
                              'source/account_module/fixed_assets',
                              'group/demo_group',).getQuantity())
    self.assertEquals(3, budget_line.getCell(
                              'product_line/1/1.1',
                              'source/account_module/fixed_assets',
                              'group/demo_group',).getQuantity())
    self.assertEquals(4, budget_line.getCell(
                              'product_line/1/1.2',
                              'source/account_module/fixed_assets',
                              'group/demo_group',).getQuantity())
    self.assertEquals(5, budget_line.getCell(
                              'product_line/1',
                              'source/account_module/goods_purchase',
                              'group/demo_group/sub2',).getQuantity())
    
    # change a cell quantity and call again
    budget_cell = budget_line.getCell(
        'product_line/1/1.2',
        'source/account_module/goods_purchase',
        'group/demo_group/sub1')
    self.assertNotEquals(None, budget_cell)
    self.assertEquals(2, budget_cell.getQuantity())
    budget_cell.setQuantity(6)

    budget_line.BudgetLine_setQuantityOnSummaryCellList()
    self.assertEquals(14, len(budget_line.contentValues()))

    self.assertEquals(1+6, budget_line.getCell(
                              'product_line/1',
                              'source/account_module/goods_purchase',
                              'group/demo_group/sub1',).getQuantity())
    self.assertEquals(4+3, budget_line.getCell(
                              'product_line/1',
                              'source/account_module/fixed_assets',
                              'group/demo_group/sub1',).getQuantity())
    self.assertEquals(1+5, budget_line.getCell(
                              'product_line/1/1.1',
                              'source/account_module/goods_purchase',
                              'group/demo_group',).getQuantity())
    self.assertEquals(1+6+5, budget_line.getCell(
                              'product_line/1',
                              'source/account_module/goods_purchase',
                              'group/demo_group',).getQuantity())

    
  def test_update_summary_cell_non_strict_and_second_summary(self):
    # test the action to create or update quantity on summary cells, variation
    # which are strict are not updated, and multiple level summary does not
    # aggregate again intermediate summaries
    budget_model = self.portal.budget_model_module.newContent(
                            portal_type='Budget Model')
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=1,
                    budget_variation='budget_cell',
                    inventory_axis='movement_strict_membership',
                    variation_base_category='product_line',)
    budget_model.newContent(
                    portal_type='Node Budget Variation',
                    int_index=2,
                    budget_variation='budget_cell',
                    inventory_axis='node',
                    variation_base_category='source',
                    aggregate_value_list=(
                      self.portal.account_module.goods_purchase,
                      self.portal.account_module.fixed_assets,
                    ))
    budget_model.newContent(
                    portal_type='Category Budget Variation',
                    int_index=3,
                    budget_variation='budget_cell',
                    inventory_axis='node_category',
                    variation_base_category='account_type',)

    budget = self.portal.budget_module.newContent(
                    portal_type='Budget',
                    start_date_range_min=DateTime(2000, 1, 1),
                    start_date_range_max=DateTime(2000, 12, 31),
                    specialise_value=budget_model)

    budget_line = budget.newContent(portal_type='Budget Line')

    # set the range, this will adjust the matrix
    budget_line.edit(
        variation_category_list=(
          'account_type/asset',
          'account_type/asset/cash',
          'account_type/asset/cash/bank',
          'source/account_module/goods_purchase',
          'product_line/1',
          'product_line/1/1.1', ))
    
    form = budget_line.BudgetLine_view
    self.portal.REQUEST.other.update(
        dict(AUTHENTICATED_USER=getSecurityManager().getUser(),

             field_membership_criterion_base_category_list=
        form.membership_criterion_base_category_list.get_value('default'),
             field_mapped_value_property_list=
        form.mapped_value_property_list.get_value('default'),
             field_matrixbox_quantity_cell_0_0_0="",
             field_matrixbox_membership_criterion_category_list_cell_0_0_0=[],
             field_matrixbox_quantity_cell_1_0_0="",
             field_matrixbox_membership_criterion_category_list_cell_1_0_0=[],
             field_matrixbox_quantity_cell_0_0_1="",
             field_matrixbox_membership_criterion_category_list_cell_0_0_1=[],
             field_matrixbox_quantity_cell_1_0_1="",
             field_matrixbox_membership_criterion_category_list_cell_1_0_1=[],
             field_matrixbox_quantity_cell_0_0_2="",
             field_matrixbox_membership_criterion_category_list_cell_0_0_2=[],
             field_matrixbox_quantity_cell_1_0_2="1",
             field_matrixbox_membership_criterion_category_list_cell_1_0_2=[
                 'product_line/1/1.1',
                 'source/account_module/goods_purchase',
                 'account_type/asset/cash/bank',
               ],
          ))
    budget_line.Base_edit(form_id=form.getId())

    self.assertEquals(1, len(budget_line.contentValues()))

    budget_line.BudgetLine_setQuantityOnSummaryCellList()
    self.assertEquals(3, len(budget_line.contentValues()))

    budget_cell = budget_line.getCell(
        'product_line/1/1.1',
        'source/account_module/goods_purchase',
        'account_type/asset/cash')
    self.assertNotEquals(None, budget_cell)
    self.assertEquals(1, budget_cell.getQuantity())

    budget_cell = budget_line.getCell(
        'product_line/1/1.1',
        'source/account_module/goods_purchase',
        'account_type/asset',)
    self.assertNotEquals(None, budget_cell)
    self.assertEquals(1, budget_cell.getQuantity())


  # Other TODOs:

  # budget level variation and budget cell level variation for same inventory
  # axis

  # resource/price currency on budget ?

  # test virtual all others when cloning an existing budget

  # predicates 


def test_suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.makeSuite(TestBudget))
  return suite
