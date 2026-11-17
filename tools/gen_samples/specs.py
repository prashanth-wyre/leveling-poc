"""Package and bid specifications.

Every dollar amount on a bid line is read from the TCJC workbook cell named by (bidder block, row).
Wording, warranties, exclusions, rates, dates and contacts are SYNTHETIC (invented for testing).
"""
from datetime import date

WB = 'wb'

PROJECT = dict(
    name='Teton County Justice Center', short='TCJC', location='Jackson, Wyoming',
    phase='FGMP / 90% Construction Documents', gc='CM/GC',
    rfp_issued=date(2025, 10, 27), addendum1=date(2025, 11, 10), bid_due=date(2025, 11, 18),
)

PACKAGES = {
    '07.50': dict(
        sheet='07.50', slug='07.50_roofing', name='Roofing', est_block='AM', scope_start=18,
        est_rows=(13, 15), scope_price=[18, 19, 20, 21, 30], scope_confirm=[29, 31, 32, 34, 36],
        spec_rows=[25, 26, 27],
        warranty_min=[('TPO roofing system (RA1, RA2)', '20-year manufacturer no-dollar-limit (NDL) total-system warranty'),
                      ('Roofing installation', '2-year installer workmanship warranty'),
                      ('Sheet metal flashing and trim', '20-year finish warranty')],
    ),
    '09.67': dict(
        sheet='09.67', slug='09.67_fluid_flooring', name='Fluid-Applied Flooring', est_block='AH', scope_start=22,
        est_rows=(13, 19), scope_price=[22, 23, 24, 25, 26, 27, 28, 29, 30, 31], scope_confirm=[], spec_rows=[],
        warranty_min=[('Resinous flooring (RN-1, RN-2) and integral cove base', '5-year joint manufacturer/installer warranty, material and labor'),
                      ('Traffic coating (TC-1)', '5-year joint manufacturer/installer warranty'),
                      ('Polished and sealed concrete (PSC-1, SC-1, SC-2, SC-4)', '1-year workmanship warranty')],
    ),
    '32.90': dict(
        sheet='32.90', slug='32.90_landscaping', name='Landscaping and Irrigation', est_block='AC', scope_start=36,
        est_rows=(13, 33),
        scope_price=[37, 38, 39, 40, 41, 42, 43, 44, 48, 50, 51, 52, 53, 54, 55, 56, 57, 58, 62, 63, 67, 68, 69, 72, 78],
        scope_confirm=[79, 80, 81, 82, 83], spec_rows=[],
        warranty_min=[('Trees, shrubs, perennials and sod', '1-year replacement warranty from Substantial Completion, no exclusions for winter kill'),
                      ('Irrigation system', '1-year warranty including first winterization and spring start-up'),
                      ('Unit pavers', '2-year warranty against settlement and displacement'),
                      ('Site furnishings', "Manufacturer's standard warranty, 3 years minimum")],
    ),
}


def L(row, desc, qty=WB, unit=WB, up=WB, amt=WB, sec=None, force_up=False):
    return dict(row=row, desc=desc, qty=qty, unit=unit, up=up, amt=amt, sec=sec, force_up=force_up)


def LS(row, desc, sec=None, amt=WB):
    """Lump-sum line: amount only, no quantity."""
    return L(row, desc, qty=None, unit=None, up=None, amt=amt, sec=sec)


def contact(n, domain):
    return dict(name='Estimating Department', phone=f'(307) 555-01{n:02d}', email=f'estimating@{domain}.example')


def rates(gf, f, j, a):
    return [('General Foreman', gf), ('Foreman', f), ('Journeyman', j), ('Apprentice', a)]


def markups(labor, material, equipment, lower):
    return [('Labor', labor), ('Material', material), ('Equipment', equipment), ('Lower-tier subcontractors', lower)]


ALT11 = 'Alternate #11 - Rooftop Photovoltaic System'
ALT12 = 'Alternate #12 - Terrazzo Flooring in lieu of Polished Concrete'

# --------------------------------------------------------------------------- 07.50 Roofing
ROOFING = [
    dict(id='superior', pkg='07.50', block='I', company='Superior Roofing, Inc.',
         file='Superior Roofing - TCJC Roofing Proposal.pdf', fmt='pdf', layout='proposal',
         accent='#1F3864', font='Helvetica', date=date(2025, 11, 18), ref='SR-25-1187', contact=contact(11, 'superior-roofing'),
         intro='Superior Roofing, Inc. is pleased to submit our proposal for Bid Package 07.50 Roofing in accordance with the 90% Construction Documents and the scope sheet issued with the invitation to bid.',
         lines=[LS(18, 'Roof Assembly RA1 - TPO membrane roofing system, complete'),
                LS(19, 'Roof Assembly RA2 - TPO membrane roofing with decorative ballast'),
                LS(20, 'Sheet metal flashing and trim, gutters, downspouts and scuppers (Section 07 62 00)'),
                L(30, 'Electronic leak detection per Section 07 54 23 (value ${up:,.0f}, carried in RA1 price)', qty=None, unit=None, amt='Included')],
         expect=934812.00, plugs=[33], alts=[(115, ALT11 + ': roof flashings and membrane work at PV supports')],
         tax='silent',
         incl=['All labor, material, equipment and supervision for a complete roofing system',
               'Roof insulation, cover board and tapered insulation as shown',
               'Joint sealants at roofing work (Section 07 92 00)',
               'Hoisting of our own materials using the project tower crane'],
         excl=['Roof deck, wood blocking and nailers', 'Roof drains and plumbing connections',
               'Snow removal and temporary heat', 'Payment and performance bond (add 1.25% if required)'],
         clar=['Proposal is based on one continuous mobilization per roof area.',
               'Pricing assumes roofing work is complete before November 1; winter installation is not included.'],
         warranty=["Manufacturer's 20-year NDL total-system warranty", '2-year installer workmanship warranty'],
         warranty_meets=True, validity=60, addenda=['Addendum 01'],
         rates=rates(98.50, 92.00, 84.75, 58.00), markups=markups('15%', '10%', '10%', '5%'),
         flags=['Sales tax status not stated (project is tax exempt) - clarify',
                'Leak detection listed as included, with a $19,878 value shown for information only',
                'Bond excluded; no flute filler or RA2 fully-adhered upgrade priced',
                'Highest of four priced bids']),

    dict(id='rodac_r0', pkg='07.50', block='N', company='Rodac', superseded_by='rodac_r1',
         file='Rodac_Roofing_Budget_Quote_110625.pdf', fmt='pdf', layout='quote',
         accent='#7A1F1F', font='Times-Roman', date=date(2025, 11, 6), ref='Q-4471', contact=contact(12, 'rodac-roofing'),
         intro='Preliminary pricing for the roofing package at the Teton County Justice Center. Final bid to follow after addenda.',
         lines=[L(18, 'TPO Roof System - Assembly RA1', qty=288, unit='SQ', up=None),
                L(19, 'TPO Roof System w/ ballast - Assembly RA2', qty=17, unit='SQ', up=None),
                L(20, 'Flashings, gutters, downspouts, scuppers', qty=None, unit=None, up=None, amt='Included')],
         expect=566700.00, plugs=None, alts=[], tax='excluded',
         incl=['Material, labor and equipment for RA1 and RA2'],
         excl=['Electronic leak detection', 'Deck flute filler insulation', 'Sales tax (tax-exempt project)'],
         clar=['Budget quote only. Will be revised on receipt of Addendum 01.'],
         warranty=["Manufacturer's 20-year NDL warranty"], warranty_meets=None, validity=30, addenda=[],
         flags=['SUPERSEDED by Rodac Rev 1 dated 2025-11-17 - must not be leveled',
                'This pre-addendum split of the Rodac number is synthetic; only Rev 1 ties to the workbook']),

    dict(id='rodac_r1', pkg='07.50', block='N', company='Rodac',
         file='Rodac_TCJC_Roofing_Bid_REV1.xlsx', fmt='xlsx', layout='estimate',
         accent='7A1F1F', font='Calibri', date=date(2025, 11, 17), ref='Q-4471 Rev 1', contact=contact(12, 'rodac-roofing'),
         intro='REVISED BID - supersedes quote Q-4471 dated 11/06/2025. Revised for Addendum 01.',
         lines=[L(18, 'TPO Roof System - Assembly RA1', qty=288, unit='SQ', up=None),
                L(19, 'TPO Roof System w/ ballast - Assembly RA2', qty=17, unit='SQ', up=None),
                L(20, 'Flashings, gutters, downspouts, scuppers', qty=None, unit=None, up=None, amt='Included'),
                LS(22, 'Acoustic flute filler insulation at deck (material supplied by steel deck sub, install only)'),
                LS(23, 'Fully adhered system at RA2'),
                LS(30, 'Electronic leak detection (ELD) per spec 075423')],
         expect=597900.00, plugs=[20, 33, 35, 38], alts=[(115, ALT11)], tax='excluded',
         incl=['Mold insurance as required for this scope', 'Housing and per diem',
               'Mobilizations as required per CM/GC schedule', 'Labor and material escalation to meet schedule',
               'LEED Silver requirements', 'Exhibit 26 scope coordination',
               'Warranties per contract documents regardless of owner material purchase',
               'OK to award roofing separately from wall panel packages'],
         excl=['Sales tax - priced as tax exempt', 'Payment and performance bond (available at our standard rate)',
               'Transition strips at dissimilar roof assemblies'],
         clar=['Quantities are in roofing squares (1 SQ = 100 SF).', 'Material cost breakout available on request.'],
         warranty=["Manufacturer's 20-year NDL total-system warranty", '2-year installer workmanship warranty',
                   '20-year finish warranty on prefinished sheet metal'],
         warranty_meets=True, validity=60, addenda=['Addendum 01'],
         rates=rates(96.00, 90.00, 82.50, 55.00), markups=markups('15%', '15%', '10%', '5%'),
         flags=['Quantities in squares, not SF', 'Flashing "Included" but workbook still carries a $100,000 CM/GC plug',
                'Bond and transition strips excluded - plugged by CM/GC ($12,955.76 and $75,000)',
                'Revised bid supersedes 2025-11-06 quote', 'Lowest leveled total; recommended in workbook']),

    dict(id='elite', pkg='07.50', block='S', company='Elite Roofing Systems',
         file='ELITE_TCJC_0750.docx', fmt='docx', layout='letter',
         accent='1B5E20', font='Georgia', date=date(2025, 11, 18), ref='ERS-2511-042', contact=contact(13, 'elite-roofing-sys'),
         intro='Thank you for the opportunity to bid the Teton County Justice Center. Elite Roofing Systems proposes to furnish and install the roofing scope as described below.',
         lines=[LS(18, 'RA1 TPO roof assembly'),
                LS(19, 'RA2 TPO roof assembly with decorative ballast'),
                LS(20, 'Sheet metal: flashing, gutters, downspouts, scuppers'),
                L(30, 'Electronic leak detection (${up:,.0f} - included in RA1 and RA2 above)', qty=None, unit=None, amt='included'),
                LS(36, 'Less sales tax on materials - tax-exempt project')],
         expect=857000.00, plugs=[33], alts=[(115, ALT11)], tax='excluded',
         incl=['Two (2) mobilizations', 'Mold insurance', 'Labor and material escalation to meet schedule',
               'LEED Silver submittals', 'Exhibit 26 scope coordination', 'Warranties per contract documents'],
         excl=['Additional mobilizations beyond two', 'Winter protection, snow and ice removal',
               'Structural deck repairs', 'Performance and payment bond'],
         clar=['The tax credit above assumes the Owner issues an exemption certificate before material purchase.'],
         warranty=["Manufacturer's 20-year NDL total-system warranty", '5-year installer workmanship warranty'],
         warranty_meets=True, validity=90, addenda=['Addendum 01'],
         rates=rates(104.00, 97.50, 88.00, 61.50), markups=markups('15%', '10%', '10%', '10%'),
         flags=['$40,000 tax-exempt credit shown as a separate deduct line',
                'Leak detection value ($54,000) stated but included in assembly prices',
                'Predicted safety incidents 30.76 - above policy threshold, needs safety approval',
                'Workmanship warranty exceeds minimum (5 years)']),

    dict(id='imperial', pkg='07.50', block='AC', company='307 Imperial Roofing',
         file='307imperial_quote_justice_center.pdf', fmt='pdf', layout='quote',
         accent='#444444', font='Courier', date=date(2025, 11, 17), ref='1093', contact=contact(14, 'imperial-roofing-307'),
         intro='Quote for roofing at the Teton County Justice Center per plans.',
         lines=[LS(18, 'TPO roof RA1'),
                LS(19, 'TPO roof RA2 with ballast'),
                LS(20, 'Flashing / gutters / downspouts / scuppers'),
                LS(30, 'Electronic leak detection'),
                LS(31, 'Mold insurance')],
         expect=852202.00, plugs=[33], alts=[(115, ALT11 + ' (PV penetration flashing only needed with this alternate)')],
         tax='included',
         incl=[],
         excl=['Bond', 'Snow removal'],
         clar=['Price is for the complete roofing package. We will not break apart scopes.'],
         warranty=["Manufacturer's 15-year standard material warranty", '1-year workmanship warranty'],
         warranty_meets=False, validity=30, addenda=[],
         flags=['Sales tax INCLUDED on a tax-exempt project, no breakout given',
                'Warranty below minimum (15-year material-only, 1-year workmanship vs 20-year NDL / 2-year)',
                'Will not split scopes', 'No addendum acknowledgement', '30-day validity (policy asks 60)']),
]

DECLINES = [
    dict(id='pinnacle', pkg='07.50', block='D', company='Pinnacle Construction',
         file='Pinnacle - no bid.docx', fmt='docx', layout='decline', accent='333333', font='Calibri',
         date=date(2025, 11, 14), contact=contact(15, 'pinnacle-construction'),
         body=['Thank you for the invitation to bid the roofing package for the Teton County Justice Center.',
               'After reviewing the documents we have decided not to submit a bid. Our crews are committed through next summer and we cannot meet the schedule shown in Attachment 4.',
               'Please keep us on your bid list for future projects.']),
    dict(id='md_roofing', pkg='07.50', block='X', company='MD Roofing',
         file='RE_ TCJC 07.50 Roofing - bid invite.pdf', fmt='pdf', layout='email', accent='#000000', font='Helvetica',
         date=date(2025, 11, 17), contact=contact(16, 'md-roofing'),
         body=['We are going to pass on this one. Too large for us right now with the bonding requirement.',
               'Thanks for thinking of us.']),
]

# --------------------------------------------------------------------------- 09.67 Fluid-Applied Flooring
FLOORING = [
    dict(id='phaze', pkg='09.67', block='D', company='Phaze Concrete Inc',
         file='Phaze Concrete - 09.67 Bid Form.xlsx', fmt='xlsx', layout='bidform',
         accent='263238', font='Arial', date=date(2025, 11, 18), ref='PC-TCJC-0967', contact=contact(21, 'phaze-concrete'),
         intro='Bid Form - Bid Package 09.67 Fluid-Applied Flooring',
         lines=[L(22, 'PSC-1 polished concrete', up=None), L(23, 'RN-1 Resinous Flooring & RFB Integral Cove Base', up=None),
                L(24, 'RN-2 Resinous Flooring & RFB Integral Cove Base', up=None), L(25, 'SC-1 sealed concrete', up=None),
                L(26, 'SC-2 sealed concrete w/ densifier', up=None), L(27, 'SC-4 sealed concrete w/ static dissipative sealant', up=None),
                L(28, 'TC-1 Traffic Coating', up=None), L(29, 'Moisture Testing', up=None)],
         expect=428000.00, plugs=[41, 42], alts=[(123, ALT12)], tax='excluded',
         incl=['Housing / per diem', 'Mobilizations as required per CM/GC schedule', 'Labor and material escalation to meet schedule', 'LEED Silver requirements'],
         excl=['Cement topping slab at detention showers (detail 34/AD53)', 'Joint filler at slab joints',
               'Polished concrete touch-up after other trades', 'Sales tax'],
         clar=['Quantities shown are our own takeoff from the 90% CD drawings.'],
         warranty=['2-year material and labor warranty on resinous flooring', '5-year warranty on traffic coating', '1-year workmanship on polished and sealed concrete'],
         warranty_meets=False, validity=60, addenda=['Addendum 01'],
         rates=rates(92.00, 86.00, 78.00, 52.00), markups=markups('15%', '15%', '15%', '10%'),
         flags=['Highest bid', 'Topping slab at detention showers not included',
                'Lump sums per item with quantities but no unit prices',
                'Resinous flooring warranty 2 years vs 5-year minimum']),

    dict(id='acs', pkg='09.67', block='I', company='Advanced Concrete Solutions',
         file='ACS Proposal 25-318 TCJC Fluid Applied Flooring.pdf', fmt='pdf', layout='proposal',
         accent='#0D47A1', font='Helvetica', date=date(2025, 11, 18), ref='25-318', contact=contact(22, 'advancedconcretesolutions'),
         intro='Advanced Concrete Solutions proposes to furnish all labor, materials and equipment for the polished concrete, sealed concrete, resinous flooring and traffic coating scope on the above project.',
         lines=[L(22, 'Polished concrete, PSC-1'), L(23, 'Resinous flooring RN-1 with integral cove base'),
                L(24, 'Resinous flooring RN-2 with integral cove base'),
                L(25, 'Sealed concrete SC-1 and SC-2 (liquid densifier at SC-2 areas)'),
                L(26, 'SC-2 densifier', qty=None, unit=None, up=None, amt='inc'),
                L(27, 'Static dissipative sealed concrete, SC-4'), L(28, 'Traffic coating TC-1'),
                L(29, 'Moisture testing', qty=None, unit=None, up=None, amt='inc'),
                L(30, 'Cement topping slab at detention showers, ref. 34/AD53')],
         expect=248337.00, plugs=[41, 42], alts=[(123, ALT12)], tax='add', tax_row=70,
         incl=['Mobilizations as required per CM/GC schedule', 'Labor and material escalation to meet schedule',
               'LEED Silver low-VOC product submittals', 'Moisture testing prior to resinous flooring installation'],
         excl=['Housing / per diem', 'Joint filler and joint sealer at sealed concrete',
               'Protection of finished floors after acceptance', 'Polished concrete touch-ups caused by other trades'],
         clar=['SC-1 and SC-2 areas are priced together at one unit rate.',
               'Sales tax on materials is not in the total above; see the tax line below.'],
         warranty=['5-year joint manufacturer/installer warranty on resinous flooring, material and labor',
                   '5-year joint warranty on traffic coating', '1-year workmanship on polished and sealed concrete'],
         warranty_meets=True, validity=60, addenda=['Addendum 01'],
         rates=rates(88.00, 82.00, 74.50, 49.00), markups=markups('15%', '10%', '10%', '5%'),
         flags=['SC-2 priced inside the SC-1 line ("inc")', 'Only bidder pricing the detention shower topping slab',
                'Sales tax ($3,891.86) quoted outside the total; workbook carries it under Insurance & Tax',
                'Housing / per diem not included', 'Lowest RESPONSIVE bidder; recommended in workbook (4th lowest price)']),

    dict(id='stewart', pkg='09.67', block='N', company='Stewart Specialty Services',
         file='Stewart Specialty - Justice Center flooring.docx', fmt='docx', layout='short',
         accent='4E342E', font='Calibri', date=date(2025, 11, 17), ref='', contact=contact(23, 'stewart-specialty'),
         intro='Pricing for concrete polishing, sealing and epoxy floors at the Justice Center.',
         lines=[L(22, 'Polish concrete PSC-1', force_up=True), L(23, 'Epoxy floor RN-1 with cove'), L(24, 'Epoxy floor RN-2 with cove'),
                L(25, 'Seal concrete SC-1'), L(26, 'Seal concrete SC-2 with densifier'), L(27, 'Seal concrete SC-4 static dissipative'),
                L(31, 'Joint filler'), L(32, 'Transportation')],
         expect=91675.03, plugs=[41, 42], alts=[], tax='silent',
         incl=[], excl=['Traffic coating', 'Moisture testing'], clar=['Based on one trip per floor.'],
         warranty=['1 year standard'], warranty_meets=False, validity=30, addenda=[],
         responsive=False,
         flags=['ARITHMETIC ERROR: 4,529 SF x $7.50 = $33,967.50 but the bid shows $33,972.03 (total overstated by $4.53); the workbook carries the bid as written',
                'Traffic coating TC-1 and moisture testing excluded; topping slab not priced',
                'Leveled total is well below the CM/GC estimate', 'No response to clarification questions - UNRESPONSIVE in workbook',
                'Tax status and addenda not addressed']),

    dict(id='centimark', pkg='09.67', block='S', company='CentiMark Corporation',
         file='CentiMark_Proposal_TetonCountyJusticeCenter.pdf', fmt='pdf', layout='proposal',
         accent='#B71C1C', font='Helvetica', date=date(2025, 11, 18), ref='CM-WY-25-0902', contact=contact(24, 'centimark'),
         intro='CentiMark Corporation proposes the following flooring systems for the referenced project.',
         lines=[L(22, 'Polished concrete system (PSC-1)', up=None), L(23, 'Resinous floor system RN-1 incl. cove base', up=None),
                L(24, 'Resinous floor system RN-2 incl. cove base', up=None),
                L(25, 'Sealed concrete - all SC types', up=None), L(28, 'Traffic coating system TC-1', up=None)],
         expect=108967.00, plugs=[41, 42], alts=[], tax='excluded',
         incl=['Housing / per diem', 'Mobilizations as required per CM/GC schedule', 'Labor and material escalation to meet schedule'],
         excl=['Cement topping slab at detention showers', 'Joint filler', 'Moisture testing and moisture mitigation',
               'LEED documentation'],
         clar=['Sealed concrete is priced as one system for all SC designations.'],
         warranty=['5-year single-source warranty on traffic coating', '1-year warranty on resinous flooring'],
         warranty_meets=False, validity=45, addenda=['Addendum 01'],
         responsive=False,
         flags=['All sealed concrete types (SC-1/SC-2/SC-4) rolled into one line of 16,218 SF',
                'Topping slab, joint filler and moisture testing excluded', 'LEED requirements not confirmed',
                'Leveled total is well below the CM/GC estimate', 'No response to clarification questions - UNRESPONSIVE in workbook']),

    dict(id='axis', pkg='09.67', block='X', company='Axis Solutions',
         file='Axis quote TCJC.docx', fmt='docx', layout='short',
         accent='000000', font='Arial', date=date(2025, 11, 18), ref='', contact=contact(25, 'axis2solutions'),
         intro='Quote - Teton County Justice Center - floor coatings',
         lines=[L(23, 'RN-1 resinous floor'), L(24, 'RN-2 cove base', up=None), L(25, 'SC-1 sealer', up=None), L(26, 'SC-2 sealer and densifier', up=None)],
         expect=56572.00, plugs=[41, 42], alts=[], tax='silent', incl=[], excl=[], clar=[],
         warranty=[], warranty_meets=False, validity=None, addenda=[],
         responsive=False,
         flags=['Quantities far off CM/GC takeoff (RN-1 525 SF vs 2,813; SC-1 53 SF vs 4,740; RN-2 priced as 200 LF)',
                'Polished concrete, SC-4 and traffic coating not priced', 'No warranty, exclusions, tax or addenda stated',
                'Not prequalified; predicted safety incidents 9.09',
                'Workbook comment: "incorrect quantities, missing scope, no responses" - UNRESPONSIVE']),

    dict(id='diverzify', pkg='09.67', block='AC', company='Diverzify Pro, LLC',
         file='Diverzify_TCJC_Div09_Resinous_LumpSum.xlsx', fmt='xlsx', layout='estimate',
         accent='00695C', font='Calibri', date=date(2025, 11, 18), ref='DZ-88412', contact=contact(26, 'diverzify'),
         intro='Lump sum proposal - fluid-applied flooring',
         lines=[LS(22, 'PSC-1 Polished Concrete - lump sum'), LS(23, 'RN-1 Resinous Flooring with RFB cove - lump sum'),
                LS(24, 'RN-2 Resinous Flooring with RFB cove - lump sum'), LS(25, 'SC-1 Sealed Concrete - lump sum'),
                LS(26, 'SC-2 Sealed Concrete with Densifier - lump sum'), LS(27, 'SC-4 Static Dissipative Sealed Concrete - lump sum'),
                L(28, 'TC-1 Traffic Coating', qty=None, unit=None, up=None, amt='NOT INCLUDED'),
                L(29, 'Moisture Testing', qty=None, unit=None, up=None, amt='inc')],
         expect=267925.00, plugs=[28, 41, 42], alts=[], tax='excluded',
         incl=['Housing / per diem', 'Mobilizations as required per CM/GC schedule', 'Labor and material escalation to meet schedule',
               'LEED Silver requirements', 'Moisture testing'],
         excl=['TC-1 traffic coating (by others)', 'Cement topping slab at detention showers', 'Sales tax'],
         clar=['Lump sum pricing only; quantities and unit prices are not provided.'],
         warranty=['10-year manufacturer material warranty on resinous flooring', '5-year labor warranty on resinous flooring',
                   '1-year workmanship on polished and sealed concrete'],
         warranty_meets=True, validity=60, addenda=['Addendum 01'],
         rates=rates(94.00, 88.50, 80.00, 54.00), markups=markups('10%', '10%', '10%', '5%'),
         flags=['Lump sums only - no quantities or unit prices', 'Traffic coating excluded; $63,342 plug (equal to the Advanced Concrete price) is inferred as a CM/GC plug',
                'Workbook applies no Textura or SDI to this bidder']),
]

# --------------------------------------------------------------------------- 32.90 Landscaping
LS_ITEMS = {
    37: ('0.3', 'Flag Pole'), 38: ('4.1', 'Park Bench with Backrest and Dividers'),
    39: ('4.2', 'Park Bench with Backrest and Integrated Table'), 40: ('4.3', 'Park Stool'), 41: ('4.4', 'Stone Bench'),
    42: ('4.5', 'Bike Rack'), 43: ('4.6', 'Litter Receptacle'), 44: ('4.7', 'Park Bench with Dividers'),
    45: (None, 'Global trade fee, shipping and handling'),
    48: ('0.6', 'Silva Cell Field System'), 50: ('5.1', 'Deciduous Trees'), 51: ('5.13', 'Evergreen Trees'), 52: ('5.4', 'Shrubs'),
    53: ('5.5', 'Grasses / Perennials / Vines'), 54: ('5.6', 'Mineral Mulch over Weed Barrier Fabric'),
    55: ('5.7', 'Mexican Beach Cobble'), 56: ('5.8', 'Wood Mulch'), 57: ('5.11', 'Sod'), 58: ('5.12', 'Landscape Edger'),
    62: (None, 'Irrigation System'), 63: (None, 'Irrigation Sleeving'),
    67: ('1.1', 'Unit Pavers'), 68: ('1.4', 'Herringbone Brick Pattern'), 69: ('1.5', 'Edge Restraint at Columns'),
    72: ('5.9', 'Tree Protection Fence'), 75: (None, 'Supervision and Mobilization'), 76: (None, 'Mobilization and Grading'),
    78: (None, 'One (1) year additional maintenance'), 79: (None, 'Soil amendments and fertilizers as needed'),
    80: (None, 'Seed stabilization'), 81: (None, 'Topsoil'), 82: (None, 'Drainage rock at site planter / retaining walls'),
    83: (None, 'Backfilling and grading of topsoil'),
}


def ls_sec(r):
    return ('Site Furnishings' if r <= 45 else 'Landscape' if r <= 58 else 'Irrigation System' if r <= 63
            else 'Paving and Surfacing' if r <= 69 else 'General')


def ls_lines(rows, style, names=None, text=None):
    names, text, out = names or {}, text or {}, []
    for r in rows:
        code, name = LS_ITEMS[r]
        name = names.get(r, name)
        if style == 'code' and code:
            d = f'{code} - {name}'
        elif style == 'paren' and code:
            d = f'{name} (legend item {code})'
        elif style == 'upper':
            d = name.upper()
        else:
            d = name
        if r in text:
            out.append(L(r, d, qty=None, unit=None, up=None, amt=text[r], sec=ls_sec(r)))
        else:
            out.append(L(r, d, sec=ls_sec(r)))
    return out


R_FURN = [37, 38, 39, 40, 41, 42, 43]
R_LAND = [48, 50, 51, 52, 53, 54, 55, 56, 57, 58]

LANDSCAPING = [
    dict(id='tree_landscape', pkg='32.90', block='D', company='The Tree And Landscape Company',
         file='Tree and Landscape Co - 32.90 Bid Form.xlsx', fmt='xlsx', layout='bidform',
         accent='2E7D32', font='Calibri', date=date(2025, 11, 18), ref='TLC-2025-207', contact=contact(31, 'tree-and-landscape'),
         intro='Bid Form - Bid Package 32.90 Landscaping and Irrigation',
         lines=ls_lines(R_FURN + R_LAND + [62, 63, 67, 72, 79, 80, 81, 83], 'code',
                        text={79: 'Included', 80: 'No Hydroseed on project', 81: 'included', 83: 'Included'}),
         expect=366791.49, plugs=[44, 49], alts=[], tax='excluded',
         incl=['Soil amendments and fertilizers as needed', 'Topsoil', 'Backfilling and grading of topsoil'],
         excl=['4.7 Park Bench with Dividers - not located on drawings', 'One year additional maintenance',
               'Drainage rock at site planter / retaining walls', 'Seed stabilization / hydroseed', 'Sales tax'],
         clar=['Silva Cell system priced per tree at 6 trees.', 'Herringbone pattern and edge restraint are included in the unit paver price.'],
         warranty=['1-year plant replacement warranty, excluding winter kill and wildlife browse', '1-year irrigation warranty',
                   '2-year warranty on unit pavers'],
         warranty_meets=False, validity=60, addenda=['Addendum 01'],
         rates=rates(78.00, 72.00, 61.50, 44.00), markups=markups('15%', '10%', '10%', '5%'),
         flags=['Park Bench 4.7 not priced - $15,000 inferred CM/GC plug', 'Silva Cell priced at 6 trees ($24,493) - $60,000 Silva Cell contingency inferred CM/GC plug',
                'Additional maintenance year and drainage rock excluded', 'Plant warranty excludes winter kill (below minimum)',
                'Bike racks: 7 (Trail Creek prices 6; DD estimate carried 9)']),

    dict(id='wlm', pkg='32.90', block='I', company='Wyoming Landscape Maintenance',
         file='WLM Proposal - Teton County Justice Center Landscape.pdf', fmt='pdf', layout='proposal',
         accent='#33691E', font='Times-Roman', date=date(2025, 11, 17), ref='WLM-2511', contact=contact(32, 'wyoming-landscape'),
         intro='Wyoming Landscape Maintenance is pleased to provide the following proposal for site furnishings, landscape, irrigation and paver installation.',
         lines=ls_lines(R_FURN + [44] + R_LAND + [62, 63, 67, 68, 69, 72, 75, 80], 'plain',
                        names={43: 'Trash receptacles', 57: 'Turf sod', 53: 'Ornamental grasses, perennials and vines', 62: 'Irrigation system, complete'},
                        text={63: 'Included', 68: 'Included above', 69: 'Included with Mexican cobble', 80: 'No Hydroseed on project'}),
         expect=546684.63, plugs=[], alts=[], tax='silent',
         incl=['Irrigation sleeving', 'Supervision for the duration of our work'],
         excl=['Seed stabilization / hydroseed', 'Winter watering', 'Rock excavation', 'Additional maintenance beyond the warranty period'],
         clar=['Prices are furnished and installed.'],
         warranty=['2-year plant replacement warranty', '2-year irrigation warranty including winterization and spring start-up',
                   '2-year warranty on unit pavers'],
         warranty_meets=True, validity=60, addenda=['Addendum 01'],
         flags=['Highest bid', 'No quantities given', 'Unit pavers ($148,719) more than double other bidders',
                'Adds its own Supervision and Mobilization line ($13,087.44)', 'Warranty exceeds minimum', 'Tax status not stated']),

    dict(id='trail_creek', pkg='32.90', block='N', company='Trail Creek Nursery Inc.',
         file='Trail Creek Nursery bid - TCJC landscape & irrigation.docx', fmt='docx', layout='letter',
         accent='5D4037', font='Cambria', date=date(2025, 11, 18), ref='TCN-1125-08', contact=contact(33, 'trailcreeknursery'),
         intro='Trail Creek Nursery Inc. offers the following bid for the landscaping and irrigation package. Our price is broken out to follow your bid form, with a few additional lines of our own at the end.',
         lines=ls_lines(R_FURN + [44, 45] + R_LAND + [62, 63, 67, 68, 69, 72, 76, 78, 79, 80, 81, 82, 83], 'paren',
                        text={68: 'Included Above', 79: 'Included in price', 80: 'Included in price', 81: 'Included in line items',
                              82: 'Included in Bid', 83: 'Included in bid under fine grade'}),
         expect=277000.00, plugs=[49], alts=[], tax='excluded',
         incl=['Soil amendments and fertilizers as needed', 'Seed stabilization', 'Topsoil', 'Drainage rock at site planter / retaining walls',
               'Fine grading of topsoil', 'One additional year of maintenance (priced above)'],
         excl=['Sales tax', 'Silva Cell quantities beyond those priced'],
         clar=['Herringbone pattern is included in the unit paver price.', 'Site furnishing prices include freight; see the shipping and handling line.',
               'We recommend the Owner carry a contingency for the Silva Cell system until the design is final.'],
         warranty=['1-year plant replacement warranty from Substantial Completion, no exclusions',
                   '1-year irrigation warranty including first winterization and spring start-up', '2-year warranty on unit pavers',
                   "Manufacturer's standard warranty on site furnishings (3 years)"],
         warranty_meets=True, validity=60, addenda=['Addendum 01'],
         rates=rates(74.00, 68.00, 58.00, 41.00), markups=markups('15%', '15%', '10%', '5%'),
         flags=['Adds its own lines: shipping and handling ($11,031), mobilization and grading ($17,000), additional maintenance year ($4,000)',
                '$60,000 Silva Cell contingency is a CM/GC plug (workbook category 52)', 'Bike racks: 6 vs 7 by another bidder',
                'Lowest leveled total; recommended in workbook']),

    dict(id='outback', pkg='32.90', block='S', company='Outback Landscape',
         file='OUTBACK LANDSCAPE - TCJC ESTIMATE.xlsx', fmt='xlsx', layout='estimate',
         accent='BF360C', font='Arial', date=date(2025, 11, 18), ref='EST-6620', contact=contact(34, 'outbacklandscape'),
         intro='Estimate - landscape, irrigation and site furnishings',
         lines=ls_lines(R_FURN + [44] + R_LAND + [62, 63, 67, 68, 69, 72, 80], 'upper', text={80: 'No Hydroseed on project'}),
         expect=459361.41, plugs=[], alts=[], tax='silent',
         incl=[], excl=['Textura or other payment system fees', 'Hydroseed', 'Winter watering'],
         clar=['Herringbone brick pattern is priced separately from unit pavers.'],
         warranty=['1-year warranty on trees and shrubs', '90-day warranty on sod', '1-year irrigation warranty', '1-year warranty on pavers'],
         warranty_meets=False, validity=30, addenda=[],
         flags=['Herringbone pattern priced as its own line ($58,543.91); others include it in unit pavers',
                'States Textura fees are not included; workbook still adds $1,012.82', 'Silva Cell ($94,120) far above other bidders',
                'Sod (90 days) and paver (1 year) warranties below minimum', 'No quantities; no addendum acknowledgement; 30-day validity']),
]

BIDS = ROOFING + FLOORING + LANDSCAPING

# --------------------------------------------------------------------------- SYNTHETIC GC-side data
# status, single-project limit ($), SDI enrolled
PREQUAL = {
    'Superior Roofing, Inc.': ('Approved', 3000000, True),
    'Rodac': ('Approved', 4000000, True),
    'Elite Roofing Systems': ('Approved with conditions (safety)', 2500000, True),
    '307 Imperial Roofing': ('Approved', 1500000, True),
    'Pinnacle Construction': ('Approved', 1000000, True),
    'MD Roofing': ('Approved', 400000, False),
    'Phaze Concrete Inc': ('Approved', 6000000, True),
    'Advanced Concrete Solutions': ('Approved', 1000000, True),
    'Stewart Specialty Services': ('Pending - financials not submitted', 250000, True),
    'CentiMark Corporation': ('Approved', 5000000, True),
    'Axis Solutions': ('Not prequalified - application incomplete', 0, True),
    'Diverzify Pro, LLC': ('Approved', 5000000, False),
    'The Tree And Landscape Company': ('Approved', 750000, True),
    'Wyoming Landscape Maintenance': ('Approved', 750000, True),
    'Trail Creek Nursery Inc.': ('Approved', 1000000, True),
    'Outback Landscape': ('Approved', 1000000, True),
}

# package, company, sent, question, response date (None = no response), response summary
CLARIFICATIONS = [
    ('07.50', 'Rodac', date(2025, 11, 19), 'Confirm tax-exempt pricing, bond rate, and whether transition strips and perimeter flashing are covered.',
     date(2025, 11, 20), 'Tax exempt confirmed. Bond available at standard rate. Flashing included; transition strips not included.'),
    ('07.50', 'Elite Roofing Systems', date(2025, 11, 19), 'Scope review call: confirm two mobilizations, leak detection, safety plan.',
     date(2025, 11, 20), 'Scope review held. All items confirmed; leak detection included. Safety mitigation plan to follow.'),
    ('07.50', '307 Imperial Roofing', date(2025, 11, 19), 'Can roofing be awarded separately? Is PV flashing in base bid? Provide tax breakout.',
     date(2025, 11, 21), 'Will not break apart. PV flashing only needed with Alternate 11. No tax breakout provided.'),
    ('09.67', 'Advanced Concrete Solutions', date(2025, 11, 19), 'Confirm SC-2 included in SC-1 line, moisture testing, and housing.',
     date(2025, 11, 20), 'SC-2 and moisture testing included. Housing / per diem not included.'),
    ('09.67', 'Diverzify Pro, LLC', date(2025, 11, 19), 'Confirm TC-1 traffic coating exclusion and provide quantities.',
     date(2025, 11, 21), 'TC-1 excluded. Lump sum only; quantities not provided.'),
    ('09.67', 'Stewart Specialty Services', date(2025, 11, 19), 'Bid is well below estimate. Confirm quantities; price TC-1, moisture testing and topping slab.',
     None, 'No response by the 2025-11-21 deadline.'),
    ('09.67', 'CentiMark Corporation', date(2025, 11, 19), 'Confirm which SC types are in the 16,218 SF; price topping slab; confirm LEED.',
     None, 'No response by the 2025-11-21 deadline.'),
    ('09.67', 'Axis Solutions', date(2025, 11, 19), 'Quantities do not match documents; polished concrete, SC-4 and TC-1 missing. Please re-quote.',
     None, 'No response by the 2025-11-21 deadline.'),
    ('32.90', 'Trail Creek Nursery Inc.', date(2025, 11, 19), 'Scope review: confirm seed stabilization, topsoil, drainage rock and Silva Cell count.',
     date(2025, 11, 20), 'All confirmed included. Silva Cell design not final; contingency recommended.'),
    ('32.90', 'The Tree And Landscape Company', date(2025, 11, 19), 'Price Park Bench 4.7 and confirm Silva Cell count.',
     date(2025, 11, 21), 'Bench 4.7 not found on drawings, not priced. Silva Cell priced at 6 trees.'),
]
