##############################################################################
#
# Copyright (c) 2002, 2005 Nexedi SARL and Contributors. All Rights Reserved.
#                    Jean-Paul Smets-Solanes <jp@nexedi.com>
#                    Romain Courteaud <romain@nexedi.com>
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

from AccessControl import ClassSecurityInfo
from Acquisition import aq_base, aq_parent, aq_inner, aq_acquire
from Products.CMFCore.utils import getToolByName

from Products.ERP5Type import Permissions, PropertySheet, Constraint, interfaces
from Products.ERP5.Document.Rule import Rule
from Products.ERP5.Document.TransformationRule import MovementFactory, TransformationRuleMixin

from zLOG import LOG

class TransformationSourcingRuleError(Exception): pass

class SourcingMovementFactory(MovementFactory):
  def __init__(self):
    self.request_list = list()

  def requestSourcing(self, **sourcing):
    self.request_list.append(sourcing)

  def getRequestList(self):
    return self.request_list

class TransformationSourcingRule(TransformationRuleMixin, Rule):
  """
  Transformation Sourcing Rule object make sure
  items required in a Transformation are sourced
  """
  # CMF Type Definition
  meta_type = 'ERP5 Transformation Sourcing Rule'
  portal_type = 'Transformation Sourcing Rule'
  # Declarative security
  security = ClassSecurityInfo()
  security.declareObjectProtected(Permissions.AccessContentsInformation)
  __implements__ = ( interfaces.IPredicate,
                     interfaces.IRule )
  # Default Properties
  property_sheets = ( PropertySheet.Base
                      , PropertySheet.XMLObject
                      , PropertySheet.CategoryCore
                      , PropertySheet.DublinCore
                      , PropertySheet.Task
                      )
  def getFactory(self):
    return SourcingMovementFactory()

  security.declareProtected(Permissions.ModifyPortalContent, 'expand')
  def expand(self, applied_rule, **kw):
    """
    Expands the current movement downward.
    -> new status -> expanded
    An applied rule can be expanded only if its parent movement
    is expanded.
    """
    parent_movement = applied_rule.getParentValue()
    explanation = self.getExplanation(movement=parent_movement)
    state = parent_movement.getCausalityValue().getPredecessorValue()
    path_list = state.getSuccessorRelatedValueList()

    if len(path_list) == 0:
      raise TransformationSourcingRuleError,\
            "Not found deliverable business path"
    if len(path_list) > 1:
      raise TransformationSourcingRuleError,\
            "Found 2 or more deliverable business path"

    path = path_list[0]

    # source, source_section
    source_section = path.getSourceSection() # only support a static access 
    source_method_id = path.getSourceMethodId()
    if source_method_id is None:
      source = path.getSource()
    else:
      source = getattr(path, source_method_id)()
    # destination, destination_section
    destination_section = path.getDestinationSection() # only support a static access 
    destination_method_id = path.getDestinationMethodId()
    if destination_method_id is None:
      destination = path.getDestination()
    else:
      destination = getattr(path, destination_method_id)()

    start_date = path.getExpectedStartDate(explanation)
    stop_date = path.getExpectedStopDate(explanation)

    quantity = parent_movement.getNetQuantity() * path.getQuantity()
    price = parent_movement.getPrice()
    if price is not None:
      price *= path.getQuantity()

    factory = self.getFactory()
    factory.requestSourcing(
      causality_value=path,
      source=source,
      source_section=source_section,
      destination=destination,
      destination_section=destination_section,
      resource=parent_movement.getResource(),
      variation_category_list=parent_movement.getVariationCategoryList(),
      variation_property_dict=parent_movement.getVariationPropertyDict(),
      quantity=quantity,
      price=price,
      quantity_unit=parent_movement.getQuantityUnit(),
      start_date=start_date,
      stop_date=stop_date,
      deliverable=1,
      )

    factory.makeMovements(applied_rule)
    Rule.expand(self, applied_rule, **kw)

