"""Scenario set 2: designed bids that exercise the plugging policy, quantity variance and unit conversion.

GC scope items and quantities come from the TCJC workbook (CM/GC estimate block of each tab).
Most bidder unit rates start from real workbook rates (value / quantity of a real bidder's column) and are then
quoted at altered quantities and in other units; rates given as plain numbers below are designed. Bidder names are FICTIONAL. Nothing here ties to the workbook totals.
"""
from datetime import date

from specs import contact

# ---- GC item references into the estimate block of the package tab
def Q(*rows): return ('q', rows)        # 90% CD or DD quantity (sum of rows)
def P(row): return ('p', row)           # DD estimate unit price
def V(row): return ('v', row)           # DD estimate line value (lump sum, or divided by qty for a rate)


def item(key, desc, unit, qty=None, rate=None, ls=None, depth=None):
    return dict(key=key, desc=desc, unit=unit, qty=qty, rate=rate, ls=ls, depth=depth)


ITEMS = {
    '07.50': [
        item('RA1', 'Roof Assembly RA1 - TPO roof assembly', 'SF', Q(18), P(14)),
        item('RA2', 'Roof Assembly RA2 - TPO roof with decorative ballast', 'SF', Q(19), P(15)),
        item('FLASH', 'Sheet metal flashing and trim, gutters, downspouts, scuppers', 'LS', ls=85000.0),
        item('ELD', 'Electronic leak detection per Section 07 54 23', 'SF', Q(18, 19), 0.75),
        item('FLUTE', 'Acoustic flute filler at roof deck (install only)', 'LS', ls=7800.0),
        item('TRANS', 'Transition strips at dissimilar roof assemblies', 'LS', ls=75000.0),
    ],
    '09.67': [
        item('PSC1', 'PSC-1 polished concrete', 'SF', Q(22), P(17)),
        item('RN1', 'RN-1 resinous flooring with integral cove base', 'SF', Q(23), P(19)),
        item('RN2', 'RN-2 resinous flooring with integral cove base', 'SF', Q(24), P(19)),
        item('SC1', 'SC-1 sealed concrete', 'SF', Q(25), P(15)),
        item('SC2', 'SC-2 sealed concrete with liquid densifier', 'SF', Q(26), P(14)),
        item('SC4', 'SC-4 sealed concrete with static dissipative sealant', 'SF', Q(27), P(13)),
        item('TC1', 'TC-1 traffic coating', 'SF', Q(28), 8.00),
        item('MOIST', 'Moisture testing', 'LS', ls=5000.0),
        item('TOP', 'Cement topping slab at detention showers (34/AD53)', 'LS', ls=10000.0),
    ],
    '32.90': [
        item('FLAG', '0.3 Flag pole', 'LS', ls=V(13)),
        item('BENCH47', '4.7 Park bench with dividers', 'EA', 1.0, P(18)),
        item('BIKE', '4.5 Bike rack', 'EA', Q(19), P(19)),
        item('SILVA', '0.6 Silva Cell field system', 'EA', Q(48), V(16)),
        item('TREES', '5.1 / 5.13 Trees, deciduous and evergreen', 'EA', Q(33), P(33)),
        item('SHRUBS', '5.4 Shrubs', 'EA', Q(32), P(32)),
        item('GRASS', '5.5 Grasses / perennials / vines', 'EA', Q(30), P(30)),
        item('MMULCH', '5.6 Mineral mulch over weed barrier fabric, 3 in. depth', 'CY', Q(25), P(25), depth=3.0),
        item('WMULCH', '5.8 Wood mulch, 3 in. depth', 'SF', Q(56), P(26), depth=3.0),
        item('SOD', '5.11 Sod', 'SF', Q(57), P(28)),
        item('IRRIG', 'Irrigation system', 'LS', ls=V(20)),
        item('SLEEVE', 'Irrigation sleeving', 'LF', Q(63), V(21)),
        item('PAVERS', '1.1 Unit pavers, herringbone pattern', 'SF', Q(67), P(17)),
        item('FENCE', '5.9 Tree protection fence', 'LF', Q(22), P(22)),
        item('DRAIN', 'Drainage rock at site planter / retaining walls', 'LS', ls=V(15)),
        item('MAINT', 'One year additional maintenance', 'LS', ls=V(23)),
    ],
}
SYNTHETIC_GC = {'FLASH', 'ELD', 'FLUTE', 'TRANS', 'TC1', 'MOIST', 'TOP'}   # GC rate/value invented, not in the workbook

# ---- unit conversions (written to gc/unit_conversions.yaml)
CONVERSIONS = dict(
    area_to_SF={'SF': 1, 'SQ': 100, 'SY': 9, 'M2': 10.7639, 'ROLL': 10},
    length_to_LF={'LF': 1, 'FT': 1, 'PANEL': 8},
    notes={
        'SQ': 'Roofing square = 100 SF',
        'SY': 'Square yard = 9 SF',
        'M2': 'Square metre = 10.7639 SF',
        'ROLL': 'Sod roll, 2 ft x 5 ft = 10 SF unless the bid states another size',
        'PANEL': 'Temporary fence panel = 8 LF unless the bid states another length',
        'CY_and_SF': 'Bulk material by volume vs area: SF = CY x 324 / depth_in ; CY = SF x depth_in / 324. '
                     'Use the depth stated in the bid; if none is stated use the specified depth.',
        'depth': 'An area quoted at a depth other than the specified depth is converted to equivalent area at the '
                 'specified depth: SF_equivalent = SF x bid_depth / spec_depth.',
    },
)

# ---- plugging policy (written to gc/plugging_policy.yaml)
POLICY = {
    'version': 1,
    'defaults': {
        'plug_when': ['excluded', 'not_priced'],
        'method': 'average_of_bidders',
        'fallback': ['gc_estimate'],
        'comparable_pool': {'exclude_self': True, 'exclude_unresponsive': True, 'min_pool': 2,
                            'outlier_trim_pct': 50, 'outlier_trim_min_pool': 3},
    },
    'quantity_normalization': {
        'convert_to': 'gc_unit', 'threshold_pct': 5.0, 'over_threshold': 'reextend_unit_rate_at_gc_quantity',
        'within_threshold': 'carry_as_bid', 'lump_sum_with_quantity': 'use_implied_unit_rate',
        'lump_sum_without_quantity': 'flag_only',
    },
    'ai_market_price': {
        'provider': 'Gemini on Vertex AI with Google Search grounding', 'region': 'Mountain West United States (Wyoming / Idaho)',
        'recency_months': 12, 'min_sources': 2, 'min_confidence': 'medium',
        'required_output': ['unit_price', 'low', 'high', 'unit', 'confidence', 'sources with url and date'],
        'acceptance_band_pct': 25, 'flag_if_deviation_from_bidder_average_pct': 25,
    },
    'methods': {
        'gc_estimate': 'CM/GC estimate for the item (unit rate x GC quantity, or the lump sum)',
        'min_of_bidders': 'Lowest leveled value among comparable bidders',
        'max_of_bidders': 'Highest leveled value among comparable bidders',
        'average_of_bidders': 'Mean leveled value of comparable bidders',
        'median_of_bidders': 'Median leveled value of comparable bidders',
        'unit_rate_x_gc_qty': 'rate_source (min | average | median | max of comparable unit rates, or gc) x GC quantity',
        'fixed_allowance': 'Stated amount',
        'ai_market_price': 'Recent market unit price found by the LLM x GC quantity',
    },
    'packages': {
        '07.50': {
            'allowances_all_bidders': [{'name': 'Additional flashing', 'amount': 50000}],
            'items': {
                'RA2': {'method': 'ai_market_price', 'fallback': ['average_of_bidders', 'gc_estimate']},
                'ELD': {'method': 'unit_rate_x_gc_qty', 'rate_source': 'median', 'fallback': ['gc_estimate']},
                'FLUTE': {'method': 'average_of_bidders', 'fallback': ['gc_estimate']},
                'TRANS': {'method': 'fixed_allowance', 'amount': 75000},
            },
            'manual_overrides': [{'bidder': 'Highline Roofing & Sheet Metal', 'item': 'FLASH', 'method': 'fixed_allowance', 'amount': 100000,
                                  'reason': 'Flashing marked "Included" with no breakout; estimator judges the included scope insufficient'}],
        },
        '09.67': {
            'allowances_all_bidders': [{'name': 'Polished concrete touch-ups', 'amount': 25000},
                                       {'name': 'Joint sealer at sealed concrete', 'amount': 32000}],
            'items': {
                'TC1': {'method': 'ai_market_price', 'fallback': ['median_of_bidders', 'gc_estimate']},
                'TOP': {'method': 'average_of_bidders', 'fallback': ['gc_estimate']},
                'MOIST': {'method': 'min_of_bidders', 'min_pool': 1, 'fallback': ['gc_estimate']},
            },
        },
        '32.90': {
            'allowances_all_bidders': [],
            'items': {
                'PAVERS': {'method': 'ai_market_price',
                           'fallback': [{'method': 'unit_rate_x_gc_qty', 'rate_source': 'average'}, 'gc_estimate']},
                'SILVA': {'method': 'ai_market_price', 'fallback': ['median_of_bidders', 'gc_estimate']},
                'BENCH47': {'method': 'median_of_bidders', 'fallback': ['gc_estimate']},
                'DRAIN': {'method': 'average_of_bidders', 'fallback': ['gc_estimate']},
                'MAINT': {'method': 'max_of_bidders', 'fallback': ['gc_estimate']},
            },
        },
    },
}

# What the AI method is asked to price (generic wording: no project or bidder names are sent).
AI_QUERIES = {
    ('07.50', 'RA2'): 'installed cost per square foot of a commercial TPO single-ply membrane roof assembly with decorative stone ballast, including insulation',
    ('09.67', 'TC1'): 'installed cost per square foot of a vehicular traffic coating (urethane traffic deck coating) on a concrete slab, commercial project',
    ('32.90', 'PAVERS'): 'installed cost per square foot of commercial clay brick unit pavers in a herringbone pattern on a prepared base',
    ('32.90', 'SILVA'): 'installed cost per unit (each 2x frame) of a Silva Cell modular suspended pavement system for street trees',
}


# ---- bid lines
def W(*rows, div='gc'):
    """Real rate from the source bidder's workbook column: sum(value cells) / div ('gc' qty, 'own' qty, or a number)."""
    return ('wb', rows, div)


def B(item, qty=None, unit=None, rate=None, status='priced', depth=None, desc=None, amount=None, note=None):
    return dict(item=item, qty=qty, unit=unit, rate=rate, status=status, depth=depth, desc=desc, amount=amount, note=note)


def bid(id, pkg, src, company, file, fmt, layout, accent, font, n, lines, intro, clar=(), excl=(), incl=(), warranty=(), ref='',
        validity=60):
    return dict(id=id, pkg=pkg, src=src, company=company, file=file, fmt=fmt, layout=layout, accent=accent, font=font,
                date=date(2025, 11, 18), ref=ref, contact=contact(n, company.lower().replace(' & ', '-').replace(' ', '-')),
                intro=intro, lines=lines, clar=list(clar), excl_extra=list(excl), incl=list(incl), warranty=list(warranty),
                validity=validity, addenda=['Addendum 01'], alts=[], tax='excluded', rates=None, markups=None)


LS, NOQ, INC, EXC, OMIT = 'ls', 'ls_noqty', 'included', 'excluded', 'omitted'

BIDS = [
    # ------------------------------------------------------------------ 07.50 Roofing
    bid('summit', '07.50', 'I', 'Summit Ridge Roofing', 'Summit Ridge Roofing - Proposal 07.50.pdf', 'pdf', 'proposal', '#1F3864', 'Helvetica', 41, [
        B('RA1', 27100, 'SF', W(18)), B('RA2', 1690, 'SF', W(19)),
        B('FLASH', status=NOQ, amount=W(20)), B('ELD', status=NOQ, amount=19878.0),
        B('FLUTE', status=EXC), B('TRANS', status=EXC)],
        'Summit Ridge Roofing submits the following unit-price proposal for the roofing package. Quantities are from our own takeoff of the roof plans.',
        clar=['Roof areas are measured to the inside face of parapets.'],
        warranty=["Manufacturer's 20-year NDL total-system warranty", '2-year installer workmanship warranty'], ref='SRR-2511-07'),
    bid('highline', '07.50', 'N', 'Highline Roofing & Sheet Metal', 'Highline_Roofing_Bid_TCJC.xlsx', 'xlsx', 'estimate', '7A1F1F', 'Calibri', 42, [
        B('RA1', 288, 'SQ', W(18)), B('RA2', 17, 'SQ', W(19)),
        B('FLASH', status=INC), B('ELD', status=NOQ, amount=W(30)), B('FLUTE', status=NOQ, amount=W(22)),
        B('TRANS', status=EXC)],
        'Roofing bid - all quantities in roofing squares',
        clar=['Quantities are in roofing squares (1 SQ = 100 SF).', 'Flashing, gutters, downspouts and scuppers are included in the assembly prices.'],
        warranty=["Manufacturer's 20-year NDL total-system warranty", '2-year installer workmanship warranty'], ref='HR-4471'),
    bid('cascade', '07.50', 'S', 'Cascade Membrane Systems', 'Cascade Membrane - TCJC roofing.docx', 'docx', 'letter', '1B5E20', 'Georgia', 43, [
        B('RA1', 30530, 'SF', W(18)), B('RA2', 1725, 'SF', W(19)),
        B('FLASH', status=NOQ, amount=W(20)), B('ELD', status=INC), B('FLUTE', status=OMIT),
        B('TRANS', status=NOQ, amount=60000.0)],
        'Cascade Membrane Systems proposes to furnish and install the roofing scope below. Our quantities include material for parapet turn-ups and waste.',
        clar=['RA1 quantity includes 6% for waste and parapet turn-ups.', 'Electronic leak detection is included in the RA1 and RA2 unit prices.'],
        warranty=["Manufacturer's 20-year NDL total-system warranty", '5-year installer workmanship warranty'], ref='CMS-25-112'),
    bid('tetonview', '07.50', 'AC', 'Tetonview Roofing', 'Tetonview quote - justice center roof (metric).pdf', 'pdf', 'quote', '#444444', 'Courier', 44, [
        B('RA1', 2676, 'M2', W(18)), B('RA2', status=EXC),
        B('FLASH', status=NOQ, amount=W(20)), B('ELD', status=EXC), B('FLUTE', status=NOQ, amount=9500.0),
        B('TRANS', status=NOQ, amount=82000.0)],
        'Quote for TPO roofing. Areas are in square metres from the manufacturer takeoff.',
        clar=['Areas are in square metres (m2).', 'Ballasted roof assembly RA2 is not included; we do not install ballasted systems.'],
        warranty=["Manufacturer's 20-year NDL warranty", '2-year workmanship warranty'], ref='2207', validity=30),

    # ------------------------------------------------------------------ 09.67 Fluid-Applied Flooring
    bid('granite', '09.67', 'I', 'Granite Peak Floor Coatings', 'Granite Peak - Proposal Fluid Applied Flooring.pdf', 'pdf', 'proposal', '#0D47A1', 'Helvetica', 51, [
        B('PSC1', 4975, 'SF', W(22, div='own')), B('RN1', 2813, 'SF', W(23, div='own')), B('RN2', 780, 'SF', W(24, div='own')),
        B('SC1', 4740, 'SF', W(25, div='own')), B('SC2', 8790, 'SF', W(25, div='own')), B('SC4', 1433, 'SF', W(27, div='own')),
        B('TC1', 7452, 'SF', W(28, div='own')), B('MOIST', status=INC), B('TOP', status=NOQ, amount=W(30))],
        'Granite Peak Floor Coatings proposes the following for the polished concrete, sealed concrete, resinous flooring and traffic coating scope.',
        clar=['Polished concrete area includes corridors 1100 through 1140, which we read as PSC-1 on the finish plans.'],
        warranty=['5-year joint warranty on resinous flooring', '5-year joint warranty on traffic coating', '1-year workmanship on concrete finishes'], ref='GP-25-318'),
    bid('northfork', '09.67', 'D', 'Northfork Polishing & Resinous', 'Northfork - 09.67 Bid Form.xlsx', 'xlsx', 'bidform', '263238', 'Arial', 52, [
        B('PSC1', 3250, 'SF', W(22, div='own')), B('RN1', 2813, 'SF', W(23, div='own')), B('RN2', 780, 'SF', W(24, div='own')),
        B('SC1', 4656, 'SF', W(25, div='own')), B('SC2', 8588, 'SF', W(26, div='own')), B('SC4', 1451, 'SF', W(27, div='own')),
        B('TC1', 7413, 'SF', W(28, div='own')), B('MOIST', status=NOQ, amount=W(29)), B('TOP', status=EXC)],
        'Bid Form - Bid Package 09.67 Fluid-Applied Flooring',
        clar=['Polished concrete excludes areas under fixed casework and equipment.'],
        warranty=['2-year warranty on resinous flooring', '5-year warranty on traffic coating'], ref='NF-0967'),
    bid('sagebrush', '09.67', 'AC', 'Sagebrush Surfaces', 'Sagebrush_Surfaces_TCJC_SY_pricing.xlsx', 'xlsx', 'estimate', '00695C', 'Calibri', 53, [
        B('PSC1', 424, 'SY', W(22)), B('RN1', 313, 'SY', W(23)), B('RN2', 87, 'SY', W(24)),
        B('SC1', 527, 'SY', W(25)), B('SC2', 977, 'SY', W(26)), B('SC4', 159, 'SY', W(27)),
        B('TC1', status=EXC), B('MOIST', status=INC), B('TOP', status=EXC)],
        'Flooring proposal - priced per square yard',
        clar=['All areas and unit prices are per square yard (SY).'],
        warranty=['10-year material warranty on resinous flooring', '5-year labor warranty on resinous flooring'], ref='SS-88412'),
    bid('bighorn', '09.67', 'N', 'Bighorn Industrial Floors', 'Bighorn floors quote.docx', 'docx', 'short', '4E342E', 'Calibri', 54, [
        B('PSC1', 3819, 'SF', 14.00), B('RN1', 2374, 'SF', 16.50), B('RN2', 641, 'SF', 19.00),
        B('SC1', status=NOQ, amount=38000.0, desc='Seal concrete, all SC types, one price'), B('SC2', status=INC), B('SC4', status=INC),
        B('TC1', status=EXC), B('MOIST', status=EXC), B('TOP', status=OMIT)],
        'Pricing for concrete polishing, sealing and epoxy floors.',
        clar=['Sealed concrete is one lump sum for all SC types.', 'We do not install traffic coatings.'], warranty=['1 year standard'], validity=30),

    # ------------------------------------------------------------------ 32.90 Landscaping
    bid('aspen', '32.90', 'D', 'Aspen Hollow Landscapes', 'Aspen Hollow - 32.90 Bid Form.xlsx', 'xlsx', 'bidform', '2E7D32', 'Calibri', 61, [
        B('FLAG', status=NOQ, amount=W(37)), B('BENCH47', status=OMIT), B('BIKE', 7, 'EA', W(42, div='own')),
        B('SILVA', status=NOQ, amount=W(48)), B('TREES', 46, 'EA', W(50, 51, div=46)), B('SHRUBS', 190, 'EA', W(52, div='own')),
        B('GRASS', 192, 'EA', W(53, div='own')), B('MMULCH', 2052, 'SF', W(54), depth=3.0, desc='5.6 Mineral mulch over weed barrier, 3 in. deep'),
        B('WMULCH', 47, 'CY', W(56), desc='5.8 Wood mulch'), B('SOD', 459, 'SY', W(57, div='own')),
        B('IRRIG', status=NOQ, amount=W(62)), B('SLEEVE', 160, 'FT', W(63, div='own')), B('PAVERS', 2150, 'SF', W(67, div='own')),
        B('FENCE', 15, 'PANEL', W(72), desc='5.9 Tree protection fence, 8 ft panels'), B('DRAIN', status=EXC), B('MAINT', status=EXC)],
        'Bid Form - Bid Package 32.90 Landscaping and Irrigation',
        clar=['Wood mulch is priced by the cubic yard at 3 in. depth.', 'Mineral mulch is priced by the square foot at 3 in. depth.',
              'Sod is priced by the square yard.', 'Tree protection fence is priced per 8 ft panel.',
              'Plant counts are from our takeoff of sheet L-201.'],
        warranty=['1-year plant replacement warranty', '1-year irrigation warranty', '2-year warranty on pavers'], ref='AHL-207'),
    bid('elkhorn', '32.90', 'I', 'Elkhorn Grounds & Irrigation', 'Elkhorn Grounds Proposal - Justice Center.pdf', 'pdf', 'proposal', '#33691E', 'Times-Roman', 62, [
        B('FLAG', status=NOQ, amount=W(37)), B('BENCH47', 1, 'EA', W(44, div=1)), B('BIKE', 9, 'EA', W(42)),
        B('SILVA', status=EXC), B('TREES', 45, 'EA', W(50, 51)), B('SHRUBS', 168, 'EA', W(52)), B('GRASS', 122, 'EA', W(53)),
        B('MMULCH', 19, 'CY', W(54)), B('WMULCH', 5104, 'SF', W(56)), B('SOD', 4133, 'SF', W(57)),
        B('IRRIG', status=NOQ, amount=W(62)), B('SLEEVE', status=INC), B('PAVERS', status=NOQ, amount=W(67)),
        B('FENCE', 120, 'LF', W(72)), B('DRAIN', status=OMIT), B('MAINT', status=EXC)],
        'Elkhorn Grounds & Irrigation is pleased to provide the following proposal for landscape, irrigation and paver installation.',
        clar=['Irrigation sleeving is included in the irrigation system price.', 'Silva Cell system is by others.'],
        warranty=['2-year plant replacement warranty', '2-year irrigation warranty', '2-year warranty on pavers'], ref='EGI-2511'),
    bid('cutthroat', '32.90', 'N', 'Cutthroat Creek Nursery', 'Cutthroat Creek Nursery bid - landscape.docx', 'docx', 'letter', '5D4037', 'Cambria', 63, [
        B('FLAG', status=NOQ, amount=W(37)), B('BENCH47', 1, 'EA', W(44, div=1)), B('BIKE', 6, 'EA', W(42, div='own')),
        B('SILVA', 24, 'EA', W(48)), B('TREES', 40, 'EA', W(50, 51)), B('SHRUBS', 168, 'EA', W(52)), B('GRASS', 122, 'EA', W(53)),
        B('MMULCH', 21, 'CY', W(54, div='own')), B('WMULCH', 5104, 'SF', 0.648 * 1.5, depth=2.0, desc='Wood mulch, 2 in. depth'),
        B('SOD', 400, 'ROLL', W(57, div='own')), B('IRRIG', status=NOQ, amount=W(62)), B('SLEEVE', 168, 'LF', W(63)),
        B('PAVERS', 239, 'SY', W(67, div='own')), B('FENCE', 120, 'LF', W(72)), B('DRAIN', status=INC),
        B('MAINT', status=NOQ, amount=W(78))],
        'Cutthroat Creek Nursery offers the following bid for the landscaping and irrigation package.',
        clar=['Wood mulch is figured at 2 in. depth, which is our standard.', 'Sod is priced per 10 sq ft roll.',
              'Unit pavers are priced per square yard.', 'Drainage rock is included in our price.'],
        warranty=['1-year plant replacement warranty, no exclusions', '1-year irrigation warranty', '2-year warranty on pavers'], ref='CCN-1125'),
    bid('windriver', '32.90', 'S', 'Wind River Site Works', 'WIND RIVER SITE WORKS - ESTIMATE.xlsx', 'xlsx', 'estimate', 'BF360C', 'Arial', 64, [
        B('FLAG', status=NOQ, amount=W(37)), B('BENCH47', 1, 'EA', W(44, div=1)), B('BIKE', 9, 'EA', W(42)),
        B('SILVA', 24, 'EA', W(48)), B('TREES', 45, 'EA', W(50, 51)), B('SHRUBS', 150, 'EA', W(52)), B('GRASS', 122, 'EA', W(53)),
        B('MMULCH', 19, 'CY', W(54)), B('WMULCH', 47, 'CY', W(56)), B('SOD', 4335, 'SF', W(57)),
        B('IRRIG', status=NOQ, amount=W(62)), B('SLEEVE', 168, 'LF', W(63)), B('PAVERS', status=EXC),
        B('FENCE', status=NOQ, amount=W(72)), B('DRAIN', status=NOQ, amount=3200.0), B('MAINT', status=NOQ, amount=6500.0)],
        'Estimate - landscape, irrigation and site furnishings',
        clar=['Wood mulch is by the cubic yard at 3 in. depth.', 'Unit pavers are by the masonry subcontractor and are not in this estimate.'],
        warranty=['1-year warranty on trees and shrubs', '90-day warranty on sod', '1-year irrigation warranty'], ref='EST-6620', validity=30),
]
