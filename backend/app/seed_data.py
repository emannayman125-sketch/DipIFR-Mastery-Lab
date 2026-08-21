from pathlib import Path
import json
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import (Question, MockExam, MockExamQuestion, Standard, Topic, PastExamSession,
                     QuestionStandardLink, QuestionCriterion)

BASE = Path(__file__).resolve().parent / "data"
STANDARD_CATALOG = json.loads((BASE / "standard_catalog.json").read_text(encoding="utf-8"))
PAST_QUESTIONS = json.loads((BASE / "past_exam_questions.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# Flagship 25-mark, Kit-style questions used to build the two "Original Mock"
# exams (Mastery Mock 1 = core standards, Mastery Mock 2 = integrated
# standards). Each has a full marking-point breakdown (QuestionCriterion
# rows) that sums to exactly 25 — the same shape as a real DipIFR marking
# scheme — instead of the single flat mark total the older 10-mark practice
# questions use. This fixes the bug where "Mastery Mock 1" could only find
# one question tagged marks==25 in the whole original bank and therefore
# never had 4 real questions.
#
# Each entry: (primary_code, extra_codes, prompt, model_answer,
#              rubric_keywords, learning_objective, marking_points)
# marking_points: list of (criterion, marks, expected_points) summing to 25.
FLAGSHIP_CORE = [
    (
        "IFRS 10", ["IFRS 3"],
        "Alpha acquired 80% of Beta's equity on 1 January for consideration of $18m cash plus contingent "
        "consideration of $2m fair value at acquisition (expected to be $2.4m at reporting date due to "
        "improved performance). At acquisition, Beta's identifiable net assets had a fair value of $17m "
        "(carrying amount $15m; the $2m fair value uplift relates to land with an indefinite life). "
        "Non-controlling interest is measured at its proportionate share of identifiable net assets. "
        "Required: (a) Calculate goodwill on acquisition. (b) Explain and calculate the year-end "
        "remeasurement of the contingent consideration. (c) Explain how the fair value uplift on land "
        "is treated on consolidation in subsequent periods.",
        "(a) Goodwill = consideration transferred ($18m cash + $2m contingent consideration fair value = "
        "$20m) plus NCI at acquisition (20% x $17m = $3.4m) less identifiable net assets at fair value "
        "($17m) = $6.4m. (b) Contingent consideration classified as a financial liability is remeasured "
        "to fair value at each reporting date with the movement ($2.4m - $2.0m = $0.4m increase) "
        "recognised in profit or loss, not against goodwill, because the remeasurement is a post-"
        "acquisition event under IFRS 3. (c) The $2m fair value uplift on land is not depreciated (land "
        "has an indefinite life) and remains as a consolidation adjustment carried at the uplifted amount "
        "each period until the land is sold or impaired, at which point the uplift affects the "
        "consolidated gain/loss on disposal or impairment loss.",
        "goodwill,consideration transferred,non-controlling interest,contingent consideration,fair value "
        "remeasurement,profit or loss,fair value uplift,indefinite life,consolidation adjustment",
        "Calculate goodwill including contingent consideration and explain its subsequent remeasurement, "
        "and the ongoing consolidation treatment of a fair-valued indefinite-life asset.",
        [
            ("Goodwill calculation — consideration transferred", 6, "$18m cash + $2m contingent consideration fair value at acquisition"),
            ("Goodwill calculation — NCI and net assets acquired", 5, "NCI at 20% x $17m FV of net assets; net assets deducted at $17m fair value, not $15m carrying amount"),
            ("Contingent consideration remeasurement", 7, "Financial liability remeasured to $2.4m; $0.4m movement recognised in profit or loss, not goodwill"),
            ("Treatment of the land fair value uplift", 7, "Indefinite life so not depreciated; uplift carried as ongoing consolidation adjustment until disposal/impairment"),
        ],
    ),
    (
        "IAS 16", ["IAS 36"],
        "On 1 January Year 1, Gamma purchased a specialised machine for $12m with a 10-year useful life "
        "and no residual value, using the cost model initially then switching to the revaluation model "
        "from 1 January Year 3. At 1 January Year 3, the machine was revalued to $11.2m. Depreciation "
        "continues on a straight-line basis over the remaining useful life. At 31 December Year 4, "
        "following a downturn in the industry, the machine's recoverable amount is estimated at $6.5m. "
        "Required: (a) Calculate the revaluation surplus recognised at 1 January Year 3. (b) Calculate "
        "the carrying amount immediately before the impairment review at 31 December Year 4. (c) "
        "Calculate and explain how the impairment loss at 31 December Year 4 should be recognised, "
        "given the revaluation surplus.",
        "(a) Carrying amount at 1 January Year 3 = $12m - (2 years x $1.2m depreciation) = $9.6m. "
        "Revaluation surplus = $11.2m - $9.6m = $1.6m, recognised in other comprehensive income and "
        "accumulated in a revaluation reserve. (b) Revised annual depreciation from Year 3 = $11.2m / 8 "
        "remaining years = $1.4m. Carrying amount at 31 December Year 4 = $11.2m - (2 years x $1.4m) = "
        "$8.4m. (c) Impairment loss = $8.4m - $6.5m recoverable amount = $1.9m. This is first recognised "
        "against the revaluation surplus relating to this asset ($1.6m, through OCI, reducing the "
        "revaluation reserve to nil), with the remaining $0.3m recognised as an expense in profit or "
        "loss, per IAS 36's interaction with revalued assets under IAS 16.",
        "revaluation surplus,revaluation reserve,other comprehensive income,depreciation,recoverable "
        "amount,impairment loss,carrying amount,revalued asset",
        "Apply IAS 16's revaluation model together with an IAS 36 impairment review on the same asset, "
        "including correct sequencing of the surplus offset.",
        [
            ("Revaluation surplus calculation", 6, "Carrying amount before revaluation $9.6m; surplus $1.6m to OCI/revaluation reserve"),
            ("Revised depreciation after revaluation", 5, "$11.2m over 8 remaining years = $1.4m per year"),
            ("Carrying amount at impairment review date", 5, "$11.2m less 2 years' revised depreciation = $8.4m"),
            ("Impairment loss recognition and allocation", 9, "Total loss $1.9m; $1.6m against revaluation reserve via OCI, $0.3m to profit or loss"),
        ],
    ),
    (
        "IFRS 15", [],
        "Delta enters a contract to supply and install specialised equipment for $900,000, with "
        "installation being a separate performance obligation from the equipment itself (each is capable "
        "of being distinct and is separately identifiable in the contract). Stand-alone selling prices "
        "are $800,000 for the equipment and $150,000 for installation. The contract also includes a "
        "performance bonus of $60,000 if installation is completed within 30 days; Delta estimates an "
        "85% probability of meeting this using the most-likely-amount method. Required: (a) Determine "
        "the transaction price. (b) Allocate the transaction price to the performance obligations. (c) "
        "Explain when revenue should be recognised for each performance obligation.",
        "(a) Transaction price = $900,000 fixed consideration + $60,000 variable consideration (bonus), "
        "included because it is highly probable the amount will not result in a significant revenue "
        "reversal given the 85% probability = $960,000. (b) Allocate based on relative stand-alone "
        "selling prices: total SSP = $950,000. Equipment: $960,000 x (800,000/950,000) = $808,421. "
        "Installation: $960,000 x (150,000/950,000) = $151,579. (c) Equipment revenue is recognised at "
        "the point in time control transfers to the customer (typically on delivery/acceptance); "
        "installation revenue is recognised over time if the customer simultaneously receives and "
        "consumes the benefit as installation progresses, otherwise at the point installation is "
        "complete and accepted.",
        "transaction price,variable consideration,most likely amount,stand-alone selling price,"
        "allocation,performance obligation,point in time,over time,control transfers",
        "Apply the five-step IFRS 15 model to a contract with distinct performance obligations and "
        "variable consideration, including allocation and timing of recognition.",
        [
            ("Transaction price including variable consideration", 6, "$900,000 + $60,000 bonus (highly probable, most-likely-amount method) = $960,000"),
            ("Allocation basis explained", 4, "Allocate using relative stand-alone selling prices, total SSP $950,000"),
            ("Equipment allocation calculation", 5, "$960,000 x 800/950 = $808,421 (or equivalent rounding)"),
            ("Installation allocation calculation", 5, "$960,000 x 150/950 = $151,579 (or equivalent rounding)"),
            ("Timing of recognition for each obligation", 5, "Equipment: point in time on transfer of control; installation: over time if criteria met, else point in time on completion"),
        ],
    ),
    (
        "IAS 12", ["IAS 19"],
        "Epsilon operates a defined benefit pension plan. At the start of the year, the plan had a "
        "net defined benefit liability of $4m. During the year: current service cost was $1.2m; the "
        "discount rate was 5%; benefits of $0.9m were paid from plan assets; and a remeasurement loss "
        "of $0.3m arose on the plan. Separately, Epsilon has an asset with a carrying amount of $5m and "
        "a tax base of $3.5m, and the applicable tax rate is 25%. Required: (a) Calculate the closing net "
        "defined benefit liability and identify where each component is recognised. (b) Calculate the "
        "deferred tax balance arising on the asset's temporary difference and state whether it is a "
        "deferred tax asset or liability.",
        "(a) Opening liability $4m + current service cost $1.2m (profit or loss) + net interest ($4m x "
        "5% = $0.2m, profit or loss) - benefits paid $0.9m (no P&L or OCI effect, settled from plan "
        "assets/liability directly) + remeasurement loss $0.3m (OCI) = closing liability of $4.8m. "
        "Service cost and net interest are recognised in profit or loss; remeasurements are recognised "
        "in other comprehensive income and are not reclassified to profit or loss in a later period. "
        "(b) Temporary difference = carrying amount $5m - tax base $3.5m = $1.5m taxable temporary "
        "difference (carrying amount exceeds tax base, meaning taxable income will be higher than "
        "accounting profit in future as the asset's benefits are realised). Deferred tax liability = "
        "$1.5m x 25% = $0.375m, recognised as a deferred tax liability.",
        "defined benefit liability,current service cost,net interest,remeasurement,other comprehensive "
        "income,profit or loss,temporary difference,tax base,deferred tax liability",
        "Roll forward a defined benefit obligation distinguishing P&L from OCI components, and calculate "
        "a deferred tax balance from a taxable temporary difference.",
        [
            ("Current service cost and net interest treatment", 6, "Both recognised in profit or loss; net interest = opening liability x discount rate"),
            ("Benefits paid treatment", 4, "No P&L/OCI impact; reduces the obligation directly"),
            ("Remeasurement treatment and closing liability", 6, "Remeasurement loss to OCI, not reclassified later; closing liability $4.8m"),
            ("Temporary difference identification", 4, "Carrying amount $5m exceeds tax base $3.5m = taxable temporary difference of $1.5m"),
            ("Deferred tax liability calculation", 5, "$1.5m x 25% = $0.375m deferred tax liability"),
        ],
    ),
]

FLAGSHIP_INTEGRATED = [
    (
        "IFRS 9", ["IAS 32"],
        "Zeta issues a convertible bond for $10m cash on 1 January. The bond has a 4-year term, pays "
        "5% annual coupon, and is convertible into a fixed number of Zeta's own equity shares at the "
        "holder's option at maturity. A similar bond without the conversion option would have required "
        "an 8% market interest rate. Required: (a) Explain why this instrument must be split into "
        "liability and equity components under IAS 32. (b) Explain how the liability component is "
        "initially measured. (c) Explain the subsequent measurement of the liability component and the "
        "equity component over the bond's life.",
        "(a) The bond contains a contractual obligation to pay cash (coupons and, absent conversion, "
        "principal) — the liability element — and an option for the holder to convert into a fixed "
        "number of equity shares — the equity element, because settlement is in a fixed number of the "
        "issuer's own equity instruments (the 'fixed-for-fixed' condition). IAS 32 requires split "
        "accounting for such compound instruments. (b) The liability component is initially measured at "
        "the present value of the contractual cash flows (coupons and principal), discounted at the 8% "
        "market rate for an equivalent bond without the conversion feature. The equity component is the "
        "residual: $10m proceeds less the liability component's present value. (c) The liability "
        "component is subsequently measured at amortised cost using the effective interest method at "
        "8%, with the difference between the effective interest charge and the cash coupon increasing "
        "the carrying amount of the liability over time. The equity component is not subsequently "
        "remeasured and remains in equity until conversion or maturity.",
        "compound instrument,fixed-for-fixed,liability component,equity component,present value,"
        "effective interest method,amortised cost,split accounting",
        "Explain and apply IAS 32's split-accounting requirement for a compound financial instrument, "
        "linking initial recognition to IFRS 9's subsequent measurement.",
        [
            ("Why the instrument is split (fixed-for-fixed)", 6, "Liability = obligation to pay cash; equity = option to receive a fixed number of shares"),
            ("Initial measurement of the liability component", 7, "PV of contractual cash flows discounted at the 8% market rate for a non-convertible equivalent"),
            ("Equity component as the residual", 4, "$10m proceeds less liability component present value"),
            ("Subsequent measurement — liability", 5, "Amortised cost using the effective interest method at 8%"),
            ("Subsequent measurement — equity", 3, "Not remeasured; remains in equity until conversion or maturity"),
        ],
    ),
    (
        "IFRS 16", ["IAS 36"],
        "Theta leases a retail unit under a 6-year lease with annual payments of $200,000 in advance, "
        "an implicit interest rate of 6%, and no purchase option. At commencement, Theta recognised a "
        "right-of-use asset and lease liability of $1,050,000. Two years later, following a downturn in "
        "footfall in the area, Theta identifies an impairment indicator for the cash-generating unit "
        "that includes this right-of-use asset. The CGU's carrying amount (including the right-of-use "
        "asset) is $2.4m and its recoverable amount is estimated at $2.1m. Required: (a) State the "
        "depreciation policy that applies to the right-of-use asset. (b) Explain how the impairment "
        "indicator and loss are assessed and allocated across the CGU, including the right-of-use asset. "
        "(c) Explain the subsequent effect of the impairment on the right-of-use asset's future "
        "depreciation charge.",
        "(a) The right-of-use asset is depreciated on a straight-line basis (unless another systematic "
        "basis better reflects the pattern of benefit) over the shorter of the lease term and the "
        "asset's useful life — here, 6 years, since there is no purchase option transferring ownership. "
        "(b) IAS 36 applies to right-of-use assets in the same way as other non-financial assets. The "
        "CGU's impairment loss is $2.4m - $2.1m = $0.3m. In the absence of goodwill in this CGU, the "
        "loss is allocated pro rata across the CGU's assets (including the right-of-use asset) based on "
        "their carrying amounts, subject to no asset being reduced below the highest of its own fair "
        "value less costs of disposal, value in use, or zero. (c) Following the impairment, the reduced "
        "carrying amount of the right-of-use asset is depreciated over its remaining useful life (the "
        "remaining lease term), resulting in a lower depreciation charge for the rest of the lease unless "
        "a subsequent reversal of impairment is recognised (which is permitted for assets other than "
        "goodwill, up to the asset's depreciated carrying amount had no impairment occurred).",
        "right-of-use asset,depreciation,shorter of lease term and useful life,cash-generating unit,"
        "impairment loss,pro rata allocation,recoverable amount,reversal of impairment",
        "Apply IFRS 16's depreciation requirement for a right-of-use asset and IAS 36's impairment "
        "testing and loss allocation when that asset sits within a wider cash-generating unit.",
        [
            ("Depreciation policy for the right-of-use asset", 5, "Straight-line over shorter of lease term and useful life; 6 years here as no purchase option"),
            ("Impairment loss calculation for the CGU", 5, "$2.4m carrying amount less $2.1m recoverable amount = $0.3m loss"),
            ("Allocation of the loss across CGU assets", 8, "Pro rata by carrying amount in absence of goodwill; asset floor rule (FVLCD/VIU/zero)"),
            ("Effect on future depreciation and possible reversal", 7, "Reduced carrying amount depreciated over remaining term; reversal permitted up to pre-impairment depreciated cost"),
        ],
    ),
    (
        "IAS 21", ["IFRS 9"],
        "Iota, whose functional currency is the dollar, sells goods to an overseas customer for "
        "€500,000 on 1 November, receivable on 31 January (3 months later). On the same date, Iota "
        "enters a forward contract to sell €500,000 on 31 January at a fixed dollar rate, designated as "
        "a cash flow hedge of the receivable. Spot rates: 1 November $1.10/€1; 31 December (year end) "
        "$1.15/€1; 31 January $1.08/€1. Required: (a) Explain how the euro receivable is translated at "
        "each reporting date under IAS 21 and where the resulting exchange differences are recognised. "
        "(b) Explain, in principle, how the effective portion of the forward contract's fair value "
        "movement is recognised while the hedge remains effective. (c) Explain what happens to the "
        "amounts recognised in other comprehensive income when the hedged transaction (cash receipt) "
        "occurs.",
        "(a) The euro receivable is a monetary item, retranslated at the closing rate at each reporting "
        "date and at settlement. At year end it is retranslated at $1.15/€1 (from $1.10/€1 at initial "
        "recognition), and at settlement at $1.08/€1 (from the $1.15/€1 carrying value). The resulting "
        "exchange differences are recognised in profit or loss for the period in which they arise, "
        "reflecting the change in the monetary item's dollar value. (b) While the hedge is highly "
        "effective, the effective portion of the gain or loss on the forward contract is recognised in "
        "other comprehensive income and accumulated in a cash flow hedge reserve within equity; any "
        "ineffective portion is recognised immediately in profit or loss. (c) When the hedged cash "
        "receipt occurs, the cumulative gain or loss previously recognised in OCI is reclassified from "
        "equity to profit or loss in the same period(s) that the hedged item (the exchange differences "
        "on the receivable) affects profit or loss, so the net effect over the life of the hedge "
        "substantially offsets the receivable's exchange rate exposure.",
        "monetary item,closing rate,exchange difference,profit or loss,cash flow hedge,hedge "
        "effectiveness,other comprehensive income,reclassification",
        "Apply IAS 21's retranslation of a monetary item together with the mechanics of cash flow hedge "
        "accounting for a related forward contract under IFRS 9.",
        [
            ("Retranslation of the receivable at each date", 8, "Monetary item retranslated at closing rate at year end and settlement; both differences quantified"),
            ("Exchange differences recognised in profit or loss", 4, "Differences on the monetary item itself go to P&L, not OCI"),
            ("Effective portion of the hedge to OCI", 7, "Effective portion of forward's fair value movement to OCI/cash flow hedge reserve; ineffective portion to P&L"),
            ("Reclassification on occurrence of the hedged transaction", 6, "Cumulative OCI amount reclassified to P&L to match when the hedged item affects profit or loss"),
        ],
    ),
    (
        "FRAMEWORK-ETHICS", ["IFRS 15"],
        "Kappa's finance director asks you, as the preparer of the financial statements, to recognise "
        "$400,000 of revenue in the current year from a contract where the performance obligation (a "
        "custom software installation) will not actually be complete and accepted by the customer until "
        "six weeks into the following year. The director argues this will help the company meet an "
        "externally communicated profit forecast. Required: (a) State, with reasons, the IFRS 15 "
        "requirement that governs when this revenue should actually be recognised. (b) Discuss the "
        "ethical and professional issues raised by the director's request and the safeguards you should "
        "apply as the preparer.",
        "(a) Under IFRS 15, revenue is recognised when (or as) the performance obligation is satisfied — "
        "i.e. when control of the promised good or service transfers to the customer. For a custom "
        "software installation that is not accepted by the customer until six weeks into the following "
        "year, control has not transferred by the current year end, so recognising the $400,000 in the "
        "current year would misstate revenue and breach IFRS 15's recognition criteria. (b) This request "
        "creates threats to the fundamental ethical principles of integrity and objectivity (pressure to "
        "misstate figures to meet an external forecast) and to professional competence and due care "
        "(being asked to apply an accounting treatment inconsistent with the applicable standard). The "
        "preparer should not comply: appropriate safeguards include clearly explaining the IFRS 15 "
        "recognition requirement to the director, documenting the technical position and the request in "
        "writing, and escalating to those charged with governance (e.g. the audit committee) if pressure "
        "continues, rather than allowing a preferred reported outcome to override compliance with the "
        "applicable IFRS Accounting Standard.",
        "control transfers,performance obligation satisfied,revenue recognition,integrity,objectivity,"
        "professional competence and due care,safeguards,those charged with governance",
        "Combine an IFRS 15 recognition-timing judgement with the ethical response required when there "
        "is management pressure to misstate the result — mirroring the real exam's embedded ethics "
        "component within a technical question.",
        [
            ("IFRS 15 recognition timing identified correctly", 8, "Control has not transferred by year end (acceptance is 6 weeks into the following year); revenue not yet recognisable"),
            ("Link between the accounting answer and the ethical dilemma", 4, "Recognises that the director's request is technically wrong, not just ethically questionable"),
            ("Ethical principles threatened", 7, "Integrity and objectivity threatened by pressure to misstate; professional competence and due care also relevant"),
            ("Appropriate safeguards / response", 6, "Explain the standard, document the position, escalate to those charged with governance if pressure continues; do not comply"),
        ],
    ),
]

# ---------------------------------------------------------------------------
# A second pair of flagship mocks (Mastery Mock 3 / 4), covering standards
# not used by Mock 1/2 above, written in ACCA's own question style and exam
# structure but with entirely original companies, figures and scenarios —
# this is original content modelled on the real exam's format, not a
# reproduction of any specific ACCA paper.
# ---------------------------------------------------------------------------
FLAGSHIP_CORE_2 = [
    (
        "IAS 2", [],
        "Lambda holds three product lines in inventory at year end. Line X cost $340,000 and has an "
        "estimated selling price of $410,000 with selling costs of $30,000. Line Y cost $220,000 but, "
        "due to a design fault discovered after year end, will require rework costing $60,000 before it "
        "can be sold for its original estimated price of $250,000, with selling costs of $15,000. Line Z "
        "cost $180,000 and is obsolete stock with no realistic buyer; scrap value is $20,000. Required: "
        "(a) State the measurement basis required by IAS 2 for inventories. (b) Calculate the amount at "
        "which each product line should be stated in the financial statements, with reasons. (c) Explain "
        "how any write-down should be presented.",
        "(a) Inventories are measured at the lower of cost and net realisable value (NRV), assessed "
        "separately for each item or group of similar items. (b) Line X: NRV = $410,000 - $30,000 = "
        "$380,000, which exceeds cost of $340,000, so stated at cost $340,000. Line Y: NRV = $250,000 - "
        "$60,000 rework - $15,000 selling costs = $175,000, which is below cost of $220,000, so stated "
        "at NRV $175,000 (a write-down of $45,000). Line Z: NRV = scrap value less any selling costs = "
        "approximately $20,000, well below cost of $180,000, so stated at $20,000 (a write-down of "
        "$160,000). (c) The write-downs (totalling $205,000) are recognised as an expense in the period "
        "in which they occur, typically within cost of sales, and inventories are subsequently monitored "
        "each period for reversal if NRV recovers, with any reversal limited to the original cost.",
        "lower of cost and net realisable value,NRV,rework costs,selling costs,write-down,cost of sales,"
        "reversal",
        "Apply IAS 2's lower-of-cost-and-NRV rule to several inventory lines with different NRV "
        "adjustments, and explain presentation of the resulting write-downs.",
        [
            ("Measurement basis stated correctly", 3, "Lower of cost and NRV, assessed item by item"),
            ("Line X calculation and conclusion", 6, "NRV $380,000 exceeds cost $340,000; stated at cost"),
            ("Line Y calculation and conclusion", 8, "NRV $175,000 after rework and selling costs; written down from $220,000"),
            ("Line Z calculation and conclusion", 5, "NRV approximates scrap value $20,000; written down from $180,000"),
            ("Presentation of the write-down", 3, "Expensed in the period, normally within cost of sales; subject to later reversal up to original cost"),
        ],
    ),
    (
        "IAS 37", [],
        "Mu is being sued by a former customer for $600,000 following a product defect. Mu's lawyers "
        "advise that it is probable Mu will lose the case, with a best estimate of the settlement at "
        "$450,000. Separately, Mu announced a restructuring plan before the year end, including detailed "
        "plans and a public announcement, expecting to spend $200,000 on employee termination benefits "
        "and $80,000 on relocating remaining staff to a different site. Required: (a) Explain whether a "
        "provision should be recognised for the lawsuit and calculate the amount. (b) Explain which "
        "elements of the restructuring costs qualify for provision recognition under IAS 37 and which do "
        "not, with reasons.",
        "(a) A provision is recognised because there is a present obligation from a past event (the "
        "product defect), it is probable that an outflow of resources will be required to settle it, and "
        "a reliable estimate can be made. The provision is recognised at the best estimate of $450,000. "
        "(b) A constructive obligation for restructuring arises because Mu has a detailed formal plan and "
        "has raised a valid expectation in those affected by starting to implement it or announcing its "
        "main features publicly. However, IAS 37 restricts restructuring provisions to costs that are "
        "both necessarily entailed by the restructuring and not associated with the entity's ongoing "
        "activities. The $200,000 employee termination benefits qualify for provision. The $80,000 "
        "relocation/retraining costs for staff who continue to be employed relate to the future conduct "
        "of the business and are not liabilities for restructuring, so they are excluded from the "
        "provision and expensed as incurred.",
        "present obligation,probable outflow,reliable estimate,provision,constructive obligation,"
        "detailed formal plan,restructuring,employee termination benefits,ongoing activities",
        "Apply the three-part recognition test for a litigation provision and the specific IAS 37 "
        "restriction on which restructuring costs qualify for provision.",
        [
            ("Recognition criteria applied to the lawsuit", 6, "Present obligation, probable outflow, reliable estimate all identified"),
            ("Lawsuit provision amount", 4, "$450,000 best estimate"),
            ("Constructive obligation for restructuring explained", 6, "Detailed formal plan plus valid expectation raised in those affected"),
            ("Termination benefits included, relocation excluded", 9, "$200,000 qualifies; $80,000 relocation/retraining relates to ongoing activities and is excluded"),
        ],
    ),
    (
        "IFRS 2", [],
        "On 1 January Year 1, Nu grants 300 share options each to 40 senior managers, conditional on "
        "them remaining in employment for 3 years. The fair value of each option at grant date is $9. At "
        "grant date, Nu estimates 5 managers will leave before the vesting date. By the end of Year 1, 3 "
        "managers have left and the estimate of total leavers over the vesting period is revised to 6. "
        "Required: (a) Explain the double entry required for equity-settled share-based payment "
        "transactions under IFRS 2. (b) Calculate the expense recognised in Year 1. (c) Explain what "
        "happens to the amounts previously recognised in equity if some options are ultimately not "
        "exercised after vesting.",
        "(a) Equity-settled share-based payment transactions are measured at the fair value of the "
        "equity instruments at grant date, and this fair value is not subsequently remeasured. The "
        "double entry each period is Dr Staff cost (profit or loss), Cr Equity (share option reserve), "
        "spread over the vesting period based on the number of instruments expected to vest. (b) Year 1 "
        "expense = (40 - 6 expected leavers) x 300 options x $9 fair value x 1/3 years = 34 x 300 x $9 x "
        "1/3 = $30,600. (c) No adjustment is made to total equity for options that vest but are "
        "subsequently not exercised — the amount already recognised in the share option reserve is "
        "simply transferred within equity (e.g. to retained earnings) rather than reversed, because the "
        "expense recognised reflected a transaction that did occur (employee service was received during "
        "the vesting period).",
        "equity-settled,fair value at grant date,not remeasured,vesting period,expected to vest,staff "
        "cost,share option reserve,transferred within equity",
        "Apply IFRS 2's grant-date fair value model with a revised leaver estimate mid-vesting, and "
        "explain the correct treatment on lapse after vesting (a commonly confused point).",
        [
            ("Double entry and grant-date fair value principle", 6, "Fair value fixed at grant date, not remeasured; Dr expense, Cr equity"),
            ("Use of revised leaver estimate for Year 1", 5, "34 managers expected to vest used, not the original 35 or actual 37 remaining"),
            ("Year 1 expense calculation", 8, "34 x 300 x $9 x 1/3 = $30,600"),
            ("Treatment of lapse after vesting", 6, "No reversal; amount transferred within equity, not credited back to profit or loss"),
        ],
    ),
    (
        "IAS 40", [],
        "Xi owns a building that it leases out to a third party under an operating lease, and Xi applies "
        "the fair value model to its investment properties. The property had a fair value of $2.4m at "
        "the start of the year. During the year, Xi spent $150,000 on improvements that extended the "
        "building's usable floor area. At year end, an independent valuer assessed the property's fair "
        "value at $2.7m before considering the improvements' effect, and separately confirmed the "
        "improvements added $180,000 of value. Required: (a) Explain why this property is classified as "
        "investment property rather than owner-occupied property, plant and equipment. (b) Calculate the "
        "carrying amount at year end under the fair value model and explain where the movement is "
        "recognised. (c) State how investment property is treated on disposal.",
        "(a) The property is held to earn rentals from a third party rather than for use in the "
        "production or supply of goods or services, or for administrative purposes, or for sale in the "
        "ordinary course of business — this meets IAS 40's definition of investment property rather than "
        "IAS 16 property, plant and equipment. (b) Under the fair value model, the property is "
        "remeasured to fair value at each reporting date with no depreciation charged. Year-end fair "
        "value = $2.7m + $180,000 = $2.88m. The improvements expenditure ($150,000) is capitalised into "
        "the asset, and the total fair value gain (($2.88m fair value) - ($2.4m opening + $150,000 "
        "improvements) = $330,000) is recognised in profit or loss for the period, not in other "
        "comprehensive income. (c) On disposal, any gain or loss (the difference between net disposal "
        "proceeds and the carrying amount) is recognised in profit or loss in the period of disposal.",
        "investment property,held to earn rentals,fair value model,no depreciation,capitalised "
        "improvements,fair value gain,profit or loss,disposal",
        "Distinguish investment property from owner-occupied PPE and apply the fair value model "
        "including capitalised subsequent expenditure.",
        [
            ("Classification as investment property justified", 5, "Held to earn rentals from a third party, not owner-occupied or for sale in the ordinary course of business"),
            ("No depreciation under the fair value model", 4, "Fair value model means remeasurement each period, no depreciation charge"),
            ("Year-end fair value calculation", 8, "$2.7m + $180,000 improvements value = $2.88m"),
            ("Fair value gain recognised in profit or loss", 8, "$330,000 gain to profit or loss, not OCI; improvements capitalised at cost first"),
        ],
    ),
]

FLAGSHIP_INTEGRATED_2 = [
    (
        "IFRS 5", ["IAS 36"],
        "Omicron decides on 1 October to sell a manufacturing division. At that date, the division "
        "meets all IFRS 5 criteria to be classified as held for sale. The division's assets had a "
        "carrying amount of $3.2m immediately before classification. Fair value less costs to sell is "
        "estimated at $2.75m. By the year end (three months later), fair value less costs to sell has "
        "risen to $2.9m, and the division has not yet been sold. Required: (a) State the conditions that "
        "must be met for the division to be classified as held for sale. (b) Calculate the amount at "
        "which the disposal group is measured at classification, and explain how any resulting loss "
        "relates to IAS 36. (c) Explain the subsequent measurement at year end, including any limit on a "
        "gain that can be recognised.",
        "(a) The asset (or disposal group) must be available for immediate sale in its present "
        "condition, the sale must be highly probable, management must be committed to a plan to sell "
        "and have initiated an active programme to locate a buyer, the asset must be actively marketed "
        "at a reasonable price, and the sale should be expected to complete within one year of "
        "classification. (b) At classification, the disposal group is measured at the lower of its "
        "carrying amount ($3.2m) and fair value less costs to sell ($2.75m), so it is written down to "
        "$2.75m. The $0.45m write-down is recognised as an impairment loss and treated in the same way "
        "as any other impairment loss under IAS 36. (c) At each subsequent reporting date the disposal "
        "group is remeasured to the lower of carrying amount and fair value less costs to sell; fair "
        "value less costs to sell has risen to $2.9m, so a gain of $0.15m may be recognised, but only up "
        "to the extent of impairment losses previously recognised ($0.45m) — the gain is not permitted "
        "to increase the disposal group's carrying amount above its original pre-impairment carrying "
        "amount of $3.2m.",
        "held for sale,available for immediate sale,highly probable,fair value less costs to sell,"
        "impairment loss,subsequent gain,limited to previously recognised losses",
        "Apply the IFRS 5 held-for-sale classification test and initial measurement, and connect the "
        "resulting write-down to IAS 36, including the capped subsequent gain rule.",
        [
            ("Held-for-sale conditions listed", 6, "Available for immediate sale, highly probable, committed plan, active marketing, expected within one year"),
            ("Initial measurement and impairment loss", 7, "Lower of carrying amount $3.2m and FVLCS $2.75m; $0.45m loss under IAS 36"),
            ("Subsequent remeasurement at year end", 6, "Remeasure to lower of carrying amount and FVLCS at each reporting date"),
            ("Cap on the subsequent gain explained", 6, "Gain of $0.15m recognisable but capped at previously recognised impairment losses of $0.45m"),
        ],
    ),
    (
        "IAS 33", ["IFRS 2"],
        "Pi had 10 million ordinary shares in issue throughout the year and reported profit for the "
        "year of $4.2m. Pi also has 800,000 share options outstanding all year with an exercise price of "
        "$3.00; the average market price of Pi's shares during the year was $4.00. Required: (a) "
        "Calculate basic earnings per share. (b) Explain, in principle, how share options are treated in "
        "calculating diluted earnings per share, using the concept of shares issued for no consideration. "
        "(c) Calculate the diluted earnings per share.",
        "(a) Basic EPS = $4.2m / 10,000,000 shares = 42 cents. (b) Under the treasury stock method used "
        "for options, it is assumed the options are exercised and the proceeds received are used to buy "
        "back shares at the average market price; the difference between the shares that would be issued "
        "on exercise and the shares that could be bought back with the proceeds represents shares issued "
        "'for no consideration', which dilutes EPS by increasing the weighted average number of shares "
        "with no corresponding increase in earnings. (c) Proceeds on exercise = 800,000 x $3.00 = "
        "$2.4m. Shares that could be repurchased at market price = $2.4m / $4.00 = 600,000 shares. "
        "Shares issued for no consideration = 800,000 - 600,000 = 200,000. Diluted weighted average "
        "shares = 10,000,000 + 200,000 = 10,200,000. Diluted EPS = $4.2m / 10,200,000 = 41.2 cents "
        "(approximately).",
        "basic earnings per share,weighted average number of shares,treasury stock method,shares issued "
        "for no consideration,exercise price,average market price,diluted earnings per share",
        "Calculate basic EPS and apply the treasury stock method to determine the dilutive effect of "
        "outstanding share options on diluted EPS.",
        [
            ("Basic EPS calculation", 5, "$4.2m / 10,000,000 = 42 cents"),
            ("Treasury stock method explained conceptually", 7, "Assumed proceeds used to buy back shares at market price; difference is shares for no consideration"),
            ("Shares for no consideration calculated", 6, "800,000 - (2.4m/4.00 = 600,000) = 200,000"),
            ("Diluted EPS calculation", 7, "$4.2m / 10,200,000 = approximately 41.2 cents"),
        ],
    ),
    (
        "IFRS 8", ["IAS 24"],
        "Rho's chief operating decision maker reviews internal reports for three operating segments: "
        "Retail (revenue $12m, of which $1m is from sales to Rho's associate, profit $2.1m, assets $9m), "
        "Wholesale (revenue $7m, profit $0.9m, assets $5m), and Logistics (revenue $3m, profit $0.2m, "
        "assets $2m). Required: (a) Apply the quantitative thresholds to determine which segments are "
        "reportable. (b) Explain why the $1m of sales to the associate is relevant to segment revenue "
        "disclosure and separately to related party disclosure. (c) State what happens to segments that "
        "do not meet any quantitative threshold.",
        "(a) Total revenue = $22m (10% threshold = $2.2m); Retail ($12m) and Wholesale ($7m) exceed this, "
        "Logistics ($3m) also exceeds it, so all three pass the revenue test alone regardless of the "
        "other tests. Reviewing overall: because total external and internal revenue of the three "
        "segments already covers effectively all of Rho's activity and each individually exceeds 10% of "
        "combined revenue, profit, or assets, all three segments (Retail, Wholesale, Logistics) are "
        "reportable operating segments under IFRS 8. (b) The $1m of sales to the associate is included "
        "within segment revenue disclosure (both external and, if applicable, inter-segment revenue must "
        "be disclosed separately) because IFRS 8 requires disclosure of revenue from transactions with "
        "other segments and material customers; separately, because the associate is a related party "
        "under IAS 24, the nature and amount of this transaction must also be disclosed as a related "
        "party transaction, as IFRS 8 does not remove the separate IAS 24 disclosure requirement. (c) "
        "Segments that do not meet any quantitative threshold may still be reported separately if "
        "management believes the information would be useful, may be combined with other similar "
        "immaterial segments, or are otherwise aggregated into an 'all other segments' category that is "
        "separately described.",
        "chief operating decision maker,quantitative thresholds,10 percent test,reportable segment,"
        "related party,segment revenue disclosure,all other segments",
        "Apply IFRS 8's quantitative thresholds to identify reportable segments and connect segment "
        "revenue disclosure to the separate IAS 24 related party disclosure requirement.",
        [
            ("10% thresholds applied to each segment", 8, "Revenue, profit and asset thresholds calculated against $22m/appropriate bases"),
            ("Conclusion — all three are reportable", 5, "Each individually exceeds at least one 10% threshold"),
            ("Segment revenue disclosure point", 6, "Inter-segment/related revenue to be separately disclosed under IFRS 8"),
            ("Related party disclosure point (IAS 24)", 6, "Separate IAS 24 disclosure still required for the associate transaction"),
        ],
    ),
    (
        "IFRS 13", ["IAS 41"],
        "Sigma holds a herd of dairy cattle, measured under IAS 41 at fair value less costs to sell. At "
        "year end, Sigma obtains three potential valuations for the herd: a quoted price for identical "
        "cattle in an active regional livestock market ($185,000), an appraisal using observable local "
        "feed and milk-price inputs adjusted for herd-specific characteristics ($179,000), and an "
        "internal cash-flow forecast based on unobservable assumptions about future milk yields "
        "($192,000). Required: (a) Explain the three-level fair value hierarchy under IFRS 13. (b) State "
        "which valuation should be used to measure the herd and to which level of the hierarchy it "
        "belongs, with reasons. (c) Explain how any costs to sell are treated in arriving at the IAS 41 "
        "measurement.",
        "(a) Level 1 inputs are quoted prices in active markets for identical assets, given the highest "
        "priority. Level 2 inputs are observable inputs other than quoted prices, such as quoted prices "
        "for similar assets or market-corroborated inputs. Level 3 inputs are unobservable inputs, used "
        "only when relevant observable inputs are not available, and given the lowest priority. (b) The "
        "quoted price for identical cattle in an active market ($185,000) should be used, because IFRS "
        "13 requires the use of the highest-priority observable inputs available, and this is a Level 1 "
        "input; the Level 2 appraisal and Level 3 forecast should not be used when a reliable Level 1 "
        "price exists for identical assets. (c) Costs to sell (e.g. transport and transaction costs "
        "necessary to sell the herd) are deducted from the fair value determined under IFRS 13 to arrive "
        "at the IAS 41 'fair value less costs to sell' measurement; they do not include costs necessary "
        "to get the herd ready for sale in the sense of production costs, only incremental disposal "
        "costs.",
        "fair value hierarchy,level 1,level 2,level 3,quoted price,active market,observable inputs,"
        "unobservable inputs,fair value less costs to sell,costs to sell",
        "Apply IFRS 13's fair value hierarchy to select the appropriate valuation for a biological asset "
        "measured under IAS 41, and explain the costs-to-sell deduction.",
        [
            ("Fair value hierarchy explained", 8, "All three levels correctly defined with the priority order"),
            ("Correct valuation selected and justified", 9, "Level 1 quoted price for identical cattle used, not Level 2 or 3"),
            ("Costs to sell treatment", 8, "Deducted from fair value to reach the IAS 41 measurement; incremental disposal costs only"),
        ],
    ),
]

# ---------------------------------------------------------------------------
# A third pair of flagship mocks (Mastery Mock 5 / 6), extending exam-quality
# (25-mark, full marking-point) coverage to standards not yet reached by
# Mocks 1-4: IAS 1, IAS 8, IAS 10, IAS 20, IAS 23, IAS 28, IAS 38, IFRS 6,
# IFRS 11, IFRS S1 and IFRS S2. Again, original companies/figures written in
# ACCA's question style — not a reproduction of any specific paper.
# ---------------------------------------------------------------------------
FLAGSHIP_CORE_3 = [
    (
        "IAS 1", [],
        "Tau's draft financial statements show a loan of $2m classified as non-current, repayable in "
        "three equal annual instalments starting 18 months after the year end. Separately, Tau's "
        "directors are aware that a major customer representing 40% of revenue is in financial "
        "difficulty and may be unable to pay $1.8m owed to Tau, though no formal insolvency proceedings "
        "have begun. Required: (a) Explain the concept of materiality under IAS 1 and how it should "
        "influence Tau's disclosure of the customer's difficulties. (b) State, with reasons, whether the "
        "loan classification is correct. (c) Explain how the going concern basis of preparation should "
        "be assessed in light of these facts.",
        "(a) Information is material if omitting, misstating or obscuring it could reasonably be "
        "expected to influence the decisions of primary users of the financial statements. Given the "
        "customer represents 40% of revenue and $1.8m is at risk, this is material by both magnitude and "
        "nature (concentration risk), so it requires disclosure, likely including a description of the "
        "risk and its potential financial statement impact, rather than being buried or omitted as "
        "immaterial. (b) The classification is incorrect: only the instalment due within 12 months of "
        "the reporting date should be classified as current; the remaining two instalments (due after 12 "
        "months) may remain non-current, but the loan should be split (current/non-current), not "
        "presented entirely as non-current. (c) Management must assess Tau's ability to continue as a "
        "going concern for at least twelve months from the reporting date, taking into account all "
        "available information, including the risk of losing $1.8m of expected cash inflow from a "
        "customer representing a significant portion of revenue; if this creates material uncertainty "
        "about the entity's ability to continue, that uncertainty must be disclosed even if the going "
        "concern basis remains appropriate.",
        "materiality,primary users,going concern,material uncertainty,current liability,non-current "
        "liability,twelve months",
        "Apply IAS 1's materiality concept to a concentration-risk disclosure judgement, test a "
        "current/non-current loan classification, and assess going concern implications together.",
        [
            ("Materiality concept and application to the disclosure", 8, "Definition applied correctly; magnitude and nature (customer concentration) both relevant"),
            ("Loan classification corrected", 8, "Only the instalment due within 12 months is current; loan should be split, not wholly non-current"),
            ("Going concern assessment explained", 9, "12-month forward assessment; material uncertainty disclosure required if applicable, even if basis remains appropriate"),
        ],
    ),
    (
        "IAS 38", [],
        "Upsilon is developing a new production process. In the year, it spent $80,000 on a feasibility "
        "study to assess technical viability (outcome uncertain at the time), followed by $210,000 "
        "designing and testing a pre-production prototype after technical feasibility was demonstrated "
        "and management approved funding to complete and use the process. A further $40,000 was spent "
        "training staff to operate the new process once it became operational. Required: (a) Explain the "
        "IAS 38 criteria that must all be met before development expenditure can be capitalised. (b) "
        "State, with reasons, how each of the three costs described should be treated. (c) Explain how "
        "the capitalised intangible asset should subsequently be amortised.",
        "(a) Development expenditure is capitalised only when the entity can demonstrate all of: "
        "technical feasibility of completing the asset; intention to complete and use or sell it; "
        "ability to use or sell it; how it will generate probable future economic benefits; availability "
        "of adequate technical, financial and other resources to complete it; and the ability to "
        "reliably measure the expenditure attributable to it. (b) The $80,000 feasibility study is "
        "research expenditure (outcome uncertain, technical feasibility not yet demonstrated) and must "
        "be expensed as incurred. The $210,000 prototype costs are incurred after feasibility was "
        "demonstrated and funding approved, meeting the IAS 38 criteria, so this is capitalised as an "
        "intangible asset. The $40,000 staff training cost is not part of bringing the asset to the "
        "condition necessary for it to operate as intended in the sense IAS 38 requires for "
        "capitalisation of directly attributable costs — training costs are expensed as incurred. (c) "
        "The capitalised intangible asset is amortised on a systematic basis over its useful life, "
        "beginning when the asset is available for use, using a method that reflects the pattern of "
        "expected consumption of its future economic benefits (straight-line if that pattern cannot be "
        "determined reliably).",
        "research expenditure,expensed,development expenditure,technical feasibility,capitalised,"
        "directly attributable costs,training costs,amortisation,useful life,available for use",
        "Distinguish research from development expenditure across a realistic sequence of project costs "
        "and apply IAS 38's capitalisation criteria and subsequent amortisation.",
        [
            ("Capitalisation criteria listed", 6, "All six IAS 38 criteria stated correctly"),
            ("Feasibility study treatment", 5, "Research expenditure; expensed as incurred"),
            ("Prototype costs treatment", 6, "Meets criteria once feasibility demonstrated and funding approved; capitalised"),
            ("Training costs treatment", 4, "Not directly attributable to bringing the asset to operating condition; expensed"),
            ("Subsequent amortisation", 4, "Systematic basis over useful life from when available for use, reflecting consumption pattern"),
        ],
    ),
    (
        "IAS 23", [],
        "Phi began construction of a qualifying new head office on 1 April, funded by a specific loan of "
        "$6m drawn down on that date at 7% annual interest. Surplus funds not immediately needed for "
        "construction were temporarily invested, earning $18,000 of investment income before being used "
        "on the project. Construction was substantially complete and ready for use on 31 December (9 "
        "months later), though minor snagging work continued into the following January. Required: (a) "
        "State the conditions for commencing and ceasing capitalisation of borrowing costs under IAS 23. "
        "(b) Calculate the borrowing costs to be capitalised for the 9-month period. (c) Explain why "
        "capitalisation stops on 31 December rather than when the snagging work is complete.",
        "(a) Capitalisation begins when expenditure on the asset is being incurred, borrowing costs are "
        "being incurred, and activities necessary to prepare the asset for its intended use are in "
        "progress; it ceases when substantially all the activities necessary to prepare the qualifying "
        "asset for its intended use are complete. (b) Borrowing costs for 9 months = $6m x 7% x 9/12 = "
        "$315,000, less investment income earned on the temporary investment of the surplus funds "
        "($18,000), giving net capitalised borrowing costs of $297,000. (c) Capitalisation ceases when "
        "the asset is substantially complete and ready for its intended use, which is a matter of "
        "substance over minor remaining tasks; because only minor snagging work remained (not activities "
        "necessary to get the asset ready for use), the building was substantially complete on 31 "
        "December and capitalisation stops then, with any subsequent borrowing costs expensed as "
        "incurred.",
        "qualifying asset,capitalisation begins,capitalisation ceases,substantially complete,specific "
        "borrowing,investment income deducted,intended use",
        "Apply IAS 23's start/stop rules for capitalisation to a specific borrowing, including deducting "
        "temporary investment income, and judge the 'substantially complete' cessation point.",
        [
            ("Commencement and cessation conditions stated", 6, "Both the start test (expenditure, costs, activities in progress) and stop test (substantially complete) explained"),
            ("Gross borrowing cost calculation", 6, "$6m x 7% x 9/12 = $315,000"),
            ("Investment income deduction", 6, "$18,000 deducted; net capitalised amount $297,000"),
            ("Cessation judgement explained", 7, "Substance over minor snagging; substantially complete on 31 December, not when every task finishes"),
        ],
    ),
    (
        "IFRS 6", [],
        "Chi, a mining entity, incurred $500,000 exploring a new site during the year, before it had "
        "obtained the legal right to explore that specific area — the exploration right was granted two "
        "months into the work once a preliminary agreement with the local authority was formalised. A "
        "further $300,000 was spent evaluating the technical feasibility and commercial viability of the "
        "mineral resource after the right was obtained, and Chi elected an accounting policy of "
        "capitalising such expenditure in line with IFRS 6. At year end, initial drilling results are "
        "discouraging and there are no further plans to develop the site. Required: (a) Explain what "
        "'exploration and evaluation expenditure' covers under IFRS 6 and the flexibility IFRS 6 permits "
        "entities in accounting for it. (b) Explain whether the $500,000 spent before obtaining the "
        "legal right qualifies as exploration and evaluation expenditure. (c) Explain how the "
        "capitalised balance should be treated given the discouraging results.",
        "(a) Exploration and evaluation expenditure is expenditure incurred in connection with the "
        "search for mineral resources, and the determination of the technical feasibility and commercial "
        "viability of extracting them, after the legal right to explore has been obtained but before the "
        "technical feasibility and commercial viability of extraction are demonstrable. IFRS 6 uniquely "
        "permits entities to continue applying their previous accounting policies for such expenditure "
        "(including capitalising some or all of it), rather than mandating a single treatment. (b) "
        "Expenditure incurred before the legal right to explore the specific area was obtained does not "
        "meet the IFRS 6 definition of exploration and evaluation expenditure (which requires the legal "
        "right to already exist), so the $500,000 falls outside IFRS 6's scope and cannot be capitalised "
        "under it; it would generally be expensed as incurred (or accounted for under another applicable "
        "standard/policy for pre-right costs). (c) Discouraging drilling results with no further "
        "development plans is an indicator of impairment under IFRS 6; the capitalised exploration and "
        "evaluation asset ($300,000) must be tested for impairment, and if the recoverable amount is "
        "below its carrying amount, an impairment loss is recognised, applying IAS 36's measurement "
        "principles as adapted by IFRS 6.",
        "exploration and evaluation expenditure,legal right to explore,accounting policy choice,"
        "capitalise or expense,impairment indicator,recoverable amount,impairment loss",
        "Apply IFRS 6's scope boundary (legal right obtained) to distinguish qualifying expenditure, and "
        "recognise and explain an impairment trigger for capitalised E&E costs.",
        [
            ("Definition and policy flexibility explained", 7, "E&E expenditure defined; IFRS 6's unique policy-continuation flexibility described"),
            ("Pre-right expenditure excluded from IFRS 6", 9, "Legal right not yet held when $500,000 was spent; falls outside IFRS 6 scope"),
            ("Impairment indicator and required response", 9, "Discouraging results = impairment indicator; test and recognise loss if recoverable amount is lower"),
        ],
    ),
]

FLAGSHIP_INTEGRATED_3 = [
    (
        "IAS 28", ["IFRS 11"],
        "Psi holds a 30% interest in Entity A and a 50% interest in a separate arrangement, Entity B, "
        "with the other 50% held by one other party. Under the contractual arrangement governing Entity "
        "B, Psi and the other party have rights to the individual assets and obligations for the "
        "liabilities of the arrangement, rather than rights to Entity B's net assets. Required: (a) "
        "Explain why Psi's 30% interest in Entity A is presumed to give significant influence, and the "
        "accounting consequence under IAS 28. (b) Explain how the structure of Entity B should be "
        "classified under IFRS 11, distinguishing a joint operation from a joint venture. (c) Explain how "
        "Psi accounts for its interest in Entity B given that classification.",
        "(a) A holding of 20% or more of the voting power is presumed to give significant influence "
        "(the ability to participate in financial and operating policy decisions, but not control), "
        "unless this presumption can be clearly rebutted; at 30%, Psi is presumed to have significant "
        "influence over Entity A, so Entity A is an associate accounted for using the equity method under "
        "IAS 28, initially recognised at cost and subsequently adjusted for Psi's share of the "
        "associate's post-acquisition profits or losses and other comprehensive income. (b) Under IFRS "
        "11, a joint arrangement is a joint operation when the parties have rights to the assets and "
        "obligations for the liabilities of the arrangement (as here, given the contractual terms), "
        "rather than a joint venture, where the parties instead have rights to the net assets of the "
        "arrangement. The legal structure alone is not decisive — the contractual terms and other facts "
        "and circumstances determine the classification, and here the terms clearly indicate a joint "
        "operation. (c) As a joint operator, Psi recognises its own assets, including its share of any "
        "jointly held assets, its own liabilities, including its share of any jointly incurred "
        "liabilities, its revenue from the sale of its share of the output, and its share of the "
        "expenses, rather than applying the equity method used for the associate or a joint venture.",
        "significant influence,20 percent presumption,equity method,associate,joint arrangement,joint "
        "operation,joint venture,rights to assets and obligations for liabilities,rights to net assets",
        "Distinguish an associate (equity method) from a joint operation (proportionate recognition of "
        "assets/liabilities/revenue/expenses) versus a joint venture (equity method), based on the "
        "substance of the contractual terms.",
        [
            ("Significant influence presumption and consequence for Entity A", 6, "20%+ presumption explained; equity method applies to the associate"),
            ("Joint operation vs joint venture distinction", 9, "Rights to assets/obligations for liabilities = joint operation; rights to net assets = joint venture; terms decide, not legal form"),
            ("Accounting for the joint operation interest", 10, "Recognise own share of assets, liabilities, revenue and expenses directly, not equity method"),
        ],
    ),
    (
        "IAS 8", ["IAS 10"],
        "Omega discovers in February (after its 31 December year end, before the financial statements "
        "are authorised for issue on 15 March) that a $600,000 expense was incorrectly capitalised as an "
        "asset in the prior year's financial statements due to a data entry error, materially overstating "
        "prior year profit and current assets. Required: (a) Explain why this discovery is an adjusting "
        "event under IAS 10. (b) Explain how the error should be corrected under IAS 8, including the "
        "effect on the comparative figures presented. (c) State what disclosure IAS 8 requires for a "
        "material prior period error.",
        "(a) Events after the reporting period are adjusting if they provide evidence of conditions that "
        "existed at the reporting date; discovering that an amount was incorrectly capitalised due to a "
        "data entry error in the prior period provides evidence about the correct treatment of a "
        "transaction that existed at (in fact, before) the reporting date, and is discovered before the "
        "financial statements are authorised for issue, so it is adjusting in the sense that the "
        "financial statements being finalised must correctly reflect the true prior period position via "
        "an IAS 8 correction, not merely a subsequent-period adjustment. (b) This is a prior period "
        "error under IAS 8 (an omission or misstatement from failing to use, or misusing, reliable "
        "information available when those statements were authorised). It is corrected retrospectively: "
        "the opening balances of assets, liabilities and equity for the earliest prior period presented "
        "are restated as if the error had never occurred, and the comparative figures for the affected "
        "prior period are restated (reducing the asset by $600,000 and reducing prior year profit, hence "
        "retained earnings, by $600,000), rather than being corrected through current period profit or "
        "loss. (c) IAS 8 requires disclosure of the nature of the prior period error, the amount of the "
        "correction for each prior period presented (for each financial statement line item affected and "
        "for basic and diluted EPS, if presented), the amount of the correction at the beginning of the "
        "earliest prior period presented, and, if retrospective restatement is impracticable, an "
        "explanation and description of how the error has been corrected.",
        "adjusting event,conditions existed at reporting date,prior period error,retrospective "
        "restatement,opening balances,comparative figures,not through current period profit or loss,"
        "disclosure of the nature and amount",
        "Combine IAS 10's adjusting-event test with IAS 8's prior period error correction mechanics "
        "(retrospective restatement) and disclosure requirements.",
        [
            ("Adjusting event reasoning under IAS 10", 6, "Evidence of conditions existing at/before the reporting date, discovered before authorisation for issue"),
            ("Correct classification as a prior period error", 5, "Error from misuse of information available when prior statements were authorised"),
            ("Retrospective restatement mechanics", 9, "Opening balances and comparatives restated; not corrected through current period profit or loss"),
            ("Required disclosures listed", 5, "Nature, amount of correction per line item/period, opening balance effect"),
        ],
    ),
    (
        "IAS 20", ["IAS 16"],
        "Beta receives a government grant of $900,000 towards the $3.6m cost of a new item of "
        "manufacturing equipment (useful life 10 years, no residual value), received in cash on the same "
        "date the equipment is brought into use. Beta's accounting policy is to present grants relating "
        "to assets as deferred income. Required: (a) Explain the two conditions that must be met before "
        "a government grant is recognised under IAS 20. (b) Explain how the grant should be presented "
        "and released to profit or loss over time, and calculate the amount released in the first full "
        "year. (c) Explain how the answer to (b) would differ under the alternative permitted "
        "presentation method.",
        "(a) A government grant is recognised only when there is reasonable assurance that the entity "
        "will comply with any conditions attached to the grant, and that the grant will actually be "
        "received. (b) Under the deferred income method, the $900,000 grant is initially recognised as "
        "deferred income (a liability) and released to profit or loss on a systematic basis over the "
        "periods in which the entity recognises the related depreciation expense as an expense — i.e. "
        "over the asset's 10-year useful life. First full year release = $900,000 / 10 = $90,000 "
        "credited to profit or loss (typically presented as other income or netted against the related "
        "expense category), matching the pattern of depreciation being expensed. (c) Under the "
        "alternative permitted method, the grant is deducted from the carrying amount of the asset "
        "($3.6m - $0.9m = $2.7m), and depreciation is then calculated on the net carrying amount "
        "($2.7m / 10 years = $270,000 per year instead of $360,000), so the profit or loss effect is a "
        "lower depreciation charge each year rather than a separate grant income line — both methods "
        "produce the same net effect on annual profit ($270,000 net charge either way: $360,000 "
        "depreciation less $90,000 grant income, versus $270,000 reduced depreciation).",
        "reasonable assurance,compliance with conditions,grant will be received,deferred income,"
        "systematic basis,matching depreciation,deducted from carrying amount,same net effect",
        "Apply IAS 20's recognition conditions and both permitted presentation methods for an "
        "asset-related grant, showing the equivalence of the net profit effect.",
        [
            ("Recognition conditions stated", 5, "Reasonable assurance of compliance and receipt, both required"),
            ("Deferred income method explained and calculated", 9, "Released over useful life matching depreciation; $90,000 in year 1"),
            ("Deduction-from-asset method explained and calculated", 8, "Net carrying amount $2.7m; depreciation $270,000 per year"),
            ("Equivalence of net effect noted", 3, "Both methods produce the same $270,000 net annual profit impact"),
        ],
    ),
    (
        "IFRS S1", ["IFRS S2"],
        "Gamma's directors are preparing their first sustainability-related disclosures alongside the "
        "financial statements and ask you to explain the new ISSB requirements. Required: (a) Explain "
        "the overall objective of IFRS S1 and the four content areas (governance, strategy, risk "
        "management, metrics and targets) it requires disclosures to be organised around. (b) Explain how "
        "IFRS S2 relates to IFRS S1 and what additional matters it specifically requires disclosure of. "
        "(c) Explain the concept of connectivity between an entity's sustainability-related financial "
        "disclosures and its financial statements.",
        "(a) IFRS S1 requires an entity to disclose information about sustainability-related risks and "
        "opportunities that could reasonably be expected to affect its cash flows, access to finance, or "
        "cost of capital over the short, medium and long term, so that users of general purpose "
        "financial reports can assess these effects. Disclosures are organised around four content "
        "areas: governance (the processes used to monitor and manage sustainability-related risks and "
        "opportunities), strategy (the approach to managing them), risk management (the processes to "
        "identify, assess, prioritise and monitor them), and metrics and targets (the entity's "
        "performance, including progress towards any targets). (b) IFRS S2 applies IFRS S1's four "
        "content areas specifically to climate-related risks and opportunities, requiring more detailed "
        "disclosures such as an entity's exposure to climate-related physical and transition risks, "
        "greenhouse gas emissions (using the Greenhouse Gas Protocol), and climate-related targets; "
        "IFRS S1 sets the general framework, and IFRS S2 is the first standard developed under it, "
        "applied together for climate matters specifically. (c) Connectivity means sustainability-"
        "related financial disclosures should be presented in a way that enables users to understand the "
        "connections between them and the related financial statements, for example by using consistent "
        "inputs and assumptions where relevant and disclosing information at the same time as the "
        "financial statements, so that sustainability information is not viewed in isolation from the "
        "entity's overall financial position and performance.",
        "sustainability-related risks and opportunities,governance,strategy,risk management,metrics and "
        "targets,IFRS S2,climate-related disclosures,greenhouse gas emissions,connectivity",
        "Explain the ISSB's general sustainability disclosure framework (IFRS S1) and its climate-"
        "specific companion standard (IFRS S2), including the connectivity principle linking them to the "
        "financial statements.",
        [
            ("IFRS S1 objective explained", 6, "Effects on cash flows, access to finance, cost of capital over short/medium/long term"),
            ("Four content areas explained", 8, "Governance, strategy, risk management, metrics and targets all correctly described"),
            ("IFRS S2's relationship to IFRS S1", 6, "Applies the same four areas specifically to climate; first standard under the S1 framework"),
            ("Connectivity concept explained", 5, "Sustainability disclosures linked to financial statements, not viewed in isolation"),
        ],
    ),
]

# ---------------------------------------------------------------------------
# Real ACCA DipIFR past-exam questions on IAS 16 / IAS 23, sourced from the
# user's own compiled study spreadsheet covering sessions not previously in
# the platform's bank: December 2017, June 2018, September 2020, December
# 2020, December 2021, June 2022 and June 2023. Each retains its real
# session as `source_round` for academic-integrity citation, and a
# calculation-driven model answer structured to match spreadsheet-mode
# working, since these are the standards students most often solve on a
# grid rather than in prose.
# ---------------------------------------------------------------------------
REAL_SESSION_IAS16_23 = [
    (
        "IAS 16", ["IAS 37"], "December 2017", 2, 9,
        "On 1 April 20X4, Delta completed the construction of a power generating facility. The total "
        "construction cost was $20 million. The facility was capable of being used from 1 April 20X4 but "
        "Delta did not bring the facility into use until 1 July 20X4. The estimated useful life of the "
        "facility at 1 April 20X4 was 40 years. Under legal regulations in the jurisdiction in which "
        "Delta operates, there are no requirements to restore the land on which power generating "
        "facilities stand to its original state at the end of the useful life of the facility. However, "
        "Delta has a reputation for conducting its business in an environmentally friendly way and has "
        "previously chosen to restore similar land even in the absence of such legal requirements. The "
        "directors of Delta estimated that the cost of restoring the land in 40 years' time (based on "
        "prices prevailing at that time) would be $10 million. A relevant annual discount rate to use in "
        "any discounting calculations is 5%. When the annual discount rate is 5%, the present value of "
        "$1 receivable in 40 years' time is approximately 14.2 cents. Required: Explain and show how the "
        "two events would be reported in the financial statements of Delta for the year ended 30 "
        "September 20X4. When considering the reporting of events in the statement of comprehensive "
        "income, you should distinguish between events being reported in profit or loss from events "
        "being reported in other comprehensive income, where this is relevant.",
        "Even without a legal obligation, Delta's consistent past practice of restoring similar land "
        "creates a constructive obligation under IAS 37, so a decommissioning provision must be "
        "recognised and included in the initial cost of the asset under IAS 16, discounted to present "
        "value. Depreciation begins when the asset is ready for its intended use (1 April 20X4), not "
        "when it is actually brought into use (1 July 20X4) — a common exam trap.\n\n"
        "Workings (spreadsheet-style):\n"
        "\tItem\tAmount ($'000)\n"
        "1\tConstruction cost\t20,000\n"
        "2\tRestoration cost (future value)\t10,000\n"
        "3\tPresent value factor (5%, 40 yrs)\t0.142\n"
        "4\tRestoration cost (present value) = 10,000 x 0.142\t1,420\n"
        "5\tTotal initial cost of asset (1+4)\t21,420\n"
        "6\tUseful life (years)\t40\n"
        "7\tDepreciation from 1 April 20X4 (ready for use), 6 months to 30 Sep 20X4 = 21,420/40 x 6/12\t268\n"
        "8\tCarrying amount at 30 Sep 20X4 (5-7)\t21,152\n"
        "9\tUnwinding of discount for the period (provision x 5% x 6/12, approx.)\t36\n"
        "10\tProvision carried at year end (4+9)\t1,456\n\n"
        "The $268 depreciation charge and the $36 unwinding-of-discount finance cost both go through "
        "profit or loss; there is no other comprehensive income impact here since this is the cost "
        "model, not a revaluation.",
        "constructive obligation,decommissioning provision,present value,discount rate,initial cost,"
        "ready for use,depreciation,unwinding of discount,finance cost,profit or loss",
        20,
    ),
    (
        "IAS 16", [], "June 2018", 4, 6,
        "When reading the accounting policies note in the consolidated financial statements, a director "
        "notices that freehold properties are measured using the fair value (revaluation) model but "
        "plant and equipment is measured using the cost model, even though both are shown within a "
        "single 'property, plant and equipment' line in the statement of financial position. The "
        "director queries why it is acceptable to measure different parts of property, plant and "
        "equipment using two different measurement models, and suggests going further by using the fair "
        "value model only for readily accessible properties and the cost model for properties in remote "
        "locations, to save time and cost. Required: Respond to the director's query, explaining the "
        "requirements of IAS 16 in this area.",
        "IAS 16 requires the measurement model (cost or revaluation) to be chosen on a class-by-class "
        "basis, not asset-by-asset — this is why freehold properties (one class) and plant and equipment "
        "(a different class) can validly use different models, since they are different classes of "
        "asset. However, the director's suggestion of splitting properties themselves — using fair value "
        "for accessible properties and cost for remote ones — is not permitted: this would mean applying "
        "two different measurement models within the same class of asset (properties), which IAS 16 does "
        "not allow purely for cost or convenience reasons. All items within a class must be measured "
        "using the same model to maintain comparability and prevent selective revaluation.",
        "class-by-class basis,measurement model,cost model,revaluation model,same class,comparability,"
        "selective revaluation not permitted",
        10,
    ),
    (
        "IAS 16", [], "September 2020", None, 8,
        "Both Alpha and Beta measure their property, plant and equipment (PPE) using the revaluation "
        "model, with remeasurement occurring at the end of each financial year. Alpha previously "
        "recorded net revaluation losses of $3.5 million, accounted for under IAS 16. For the year ended "
        "31 March 20X5, Alpha recorded remeasurement gains of $5 million relating to properties that had "
        "previously suffered losses. Beta, on the other hand, has only ever recorded revaluation gains, "
        "with all depreciation and impairments of PPE recognised in cost of sales. Required: Explain how "
        "Alpha's revaluation gain should be recognised, and comment on whether Beta's policy of "
        "recognising all depreciation and impairments in cost of sales is consistent with IAS 16.",
        "Under IAS 16, a revaluation gain is recognised in other comprehensive income and accumulated in "
        "a revaluation surplus, except to the extent that it reverses a revaluation decrease of the same "
        "asset previously recognised in profit or loss, in which case the reversal is recognised in "
        "profit or loss to that extent. For Alpha: of the $5 million gain, $3.5 million reverses the "
        "previous loss recognised in profit or loss (cost of sales/similar) and should therefore be "
        "recognised in profit or loss; the remaining $1.5 million is recognised in other comprehensive "
        "income.\n\n"
        "Workings:\n\tItem\tAmount ($'000)\n1\tAlpha prior revaluation loss (recognised in P&L)\t-3,500\n"
        "2\tAlpha current year revaluation gain\t5,000\n3\tPortion reversing prior loss, to P&L (min of 1 and 2)\t3,500\n"
        "4\tRemaining portion, to OCI (2-3)\t1,500\n\n"
        "Beta's policy of recognising all impairments in cost of sales is generally consistent with IAS "
        "16/IAS 36 (impairment losses on a revalued asset are recognised in OCI only to the extent of any "
        "revaluation surplus for that asset, with any excess to profit or loss). However, recognising "
        "*all* depreciation in cost of sales is a presentation choice within profit or loss and does not "
        "in itself breach IAS 16, provided depreciation is still calculated correctly on the revalued "
        "carrying amount.",
        "revaluation gain,other comprehensive income,reversal of previous loss,profit or loss,"
        "revaluation surplus,impairment,cost of sales",
        16,
    ),
    (
        "IAS 16", ["IAS 23"], "December 2020", None, 15,
        "On 1 November 20X4, Gamma placed an order for machinery for a new business venture. The initial "
        "cost was $30 million, delivered on 30 November 20X4. The machine required further development "
        "and installation at Gamma's premises, carried out by the supplier from 1 December 20X4 to 30 "
        "April 20X5, at an additional cost of $60 million; Gamma paid the total $90 million (net of two "
        "months' credit) on 30 June 20X5. Following installation, employees attended a training course "
        "completed on 15 May 20X5 at a cost of $1 million. A government safety certificate, legally "
        "required before the machinery could be used, was issued on 31 May 20X5 at a cost of $600,000, "
        "paid 30 June 20X5. Due to economic uncertainty, the machinery was not brought into use until 31 "
        "July 20X5. The venture qualifies for a preferential 12-month loan at 4% per annum, available "
        "only on 1 November each year; Gamma borrowed $90 million on 1 November 20X4 and repaid it with "
        "accrued interest on 31 October 20X5. The estimated useful life of the machinery is ten years, "
        "but its engine (current replacement cost $24 million; estimated replacement cost in five years' "
        "time $30 million) will need replacing after five years. Required: Explain and show how these "
        "events would be reported in Gamma's financial statements for the year ended 30 September 20X5.",
        "The machine (excluding the separately-identifiable engine component) and its installation costs "
        "and safety certificate are capitalised under IAS 16, since they are necessary to bring the asset "
        "to the location and condition for its intended operation; training costs are not capitalisable "
        "and are expensed. Borrowing costs on the specific qualifying-asset loan are capitalised while "
        "construction/installation activities are in progress. The engine must be depreciated separately "
        "from the rest of the machine (component depreciation) because it has a materially different "
        "useful life. Depreciation begins when the asset is ready for use (after installation and safety "
        "certification), not when actually brought into use.\n\n"
        "Workings:\n\tItem\tAmount ($'000)\n1\tInitial cost\t30,000\n2\tInstallation/development cost\t60,000\n"
        "3\tSafety certificate cost (capitalised)\t600\n4\tTraining cost (expensed, not capitalised)\t1,000\n"
        "5\tBorrowing cost capitalised (90,000 x 4% x 6/12, Dec-May activities in progress)\t1,800\n"
        "6\tTotal capitalised cost (1+2+3+5)\t92,400\n"
        "7\tEngine component (current replacement cost, used as proxy for allocation)\t24,000\n"
        "8\tRemaining asset component (6-7)\t68,400\n"
        "9\tEngine depreciation (24,000/5 years)\t4,800 per year\n"
        "10\tRemaining asset depreciation (68,400/10 years)\t6,840 per year\n\n"
        "Only a proportion of a full year's depreciation is charged from the date the asset was ready for "
        "use to the 30 September 20X5 year end. The $1 million training cost is expensed to profit or "
        "loss as incurred.",
        "capitalised installation cost,safety certificate,training cost expensed,borrowing cost "
        "capitalised,qualifying asset,component depreciation,separate useful life,ready for use",
        25,
    ),
    (
        "IAS 16", ["IAS 37"], "December 2021", None, 15,
        "On 1 November 20X4, Gamma commenced construction of a power plant at a total cost of $30 "
        "million, completed 28 February 20X5, and brought into use 31 March 20X5. The estimated useful "
        "life is 20 years from the date it is first depreciated. Construction caused environmental "
        "damage; the directors estimate rectification at the end of the plant's useful life would cost "
        "$20 million. There is no legal requirement to carry out this work, but Gamma has always "
        "rectified environmental damage it has caused in the past, regardless of legal obligation. An "
        "appropriate discount rate is 8% per annum; the present value of $1 payable in 20 years' time at "
        "this rate is approximately 21 cents. Required: Explain and show how these events would be "
        "reported in Gamma's financial statements for the year ended 30 September 20X5.",
        "As in the December 2017-style scenario, Gamma's consistent past practice of rectifying "
        "environmental damage even without a legal obligation creates a constructive obligation under "
        "IAS 37, requiring a decommissioning provision included in the initial cost of the asset at "
        "present value. Depreciation begins from the date the asset is ready for its intended use (28 "
        "February 20X5, when construction completed), not the later date it was actually brought into "
        "use (31 March 20X5).\n\n"
        "Workings:\n\tItem\tAmount ($'000)\n1\tConstruction cost\t30,000\n2\tRectification cost (future "
        "value)\t20,000\n3\tPresent value factor (8%, 20 yrs)\t0.21\n4\tRectification cost (present "
        "value) = 20,000 x 0.21\t4,200\n5\tTotal initial cost (1+4)\t34,200\n6\tUseful life (years)\t20\n"
        "7\tDepreciation from 28 Feb 20X5 (ready for use), approx. 7 months to 30 Sep 20X5 = "
        "34,200/20 x 7/12\t998\n8\tCarrying amount at year end (5-7)\t33,202\n"
        "9\tUnwinding of discount for the period (provision x 8% x 7/12, approx.)\t196\n"
        "10\tProvision carried at year end (4+9)\t4,396\n\n"
        "The double entry for the unwinding of the discount is Dr Finance cost (profit or loss), Cr "
        "Provision — the finance cost is charged to profit or loss each period as the provision accretes "
        "towards its eventual settlement amount.",
        "constructive obligation,decommissioning provision,present value,ready for use,depreciation,"
        "unwinding of discount,finance cost,provision",
        20,
    ),
    (
        "IAS 16", ["IAS 23"], "June 2022", None, 12,
        "On 1 August 20X4, Alpha began constructing a power plant at a cost of $60 million, completed 30 "
        "November 20X4 and available for use from that date, though it was not brought into use (after a "
        "formal opening ceremony) until 1 January 20X5. The estimated useful life is 10 years. Alpha "
        "borrowed $60 million on 1 July 20X4 specifically to finance the construction, at 8% per annum "
        "interest payable in arrears on 30 June each year. At 31 March 20X5, Alpha's draft PPE figure "
        "incorrectly included $62.01 million for the power plant, made up of the $60 million construction "
        "cost, $3.6 million of finance cost on the loan calculated over 9 months (1 July 20X4 to 31 March "
        "20X5), less $1.59 million of depreciation calculated from 1 January 20X5 (3 months) at 63,600/10 "
        "x 3/12. Required: Identify and correct the errors in the draft PPE figure.",
        "Two errors exist in the draft calculation. First, borrowing costs should only be capitalised "
        "while construction is actively in progress — capitalisation must cease when the asset is "
        "substantially complete and ready for use (30 November 20X4), not continue for the full 9 months "
        "to 31 March 20X5. Second, depreciation should begin from when the asset is ready for its "
        "intended use (30 November 20X4), not from when it was actually brought into use after the "
        "opening ceremony (1 January 20X5).\n\n"
        "Workings (corrected):\n\tItem\tAmount ($'000)\n1\tConstruction cost\t60,000\n"
        "2\tBorrowing cost capitalised, 1 Jul-30 Nov 20X4 only (4 months) = 60,000 x 8% x 4/12\t1,600\n"
        "3\tCorrected total cost (1+2)\t61,600\n4\tDepreciation from 30 Nov 20X4 (4 months to 31 Mar "
        "20X5) = 61,600/10 x 4/12\t2,053\n5\tCorrected carrying amount (3-4)\t59,547\n"
        "6\tOriginally recognised (per draft)\t62,010\n7\tOverstatement to correct (6-5)\t2,463\n\n"
        "The correcting entry is Dr Retained earnings, Cr Property, plant and equipment for $2.463 "
        "million, reflecting both the excess borrowing cost wrongly capitalised for the 5 months after "
        "completion and the depreciation that should have been charged from 30 November rather than 1 "
        "January.",
        "borrowing cost capitalisation ceases,substantially complete,ready for use,depreciation start "
        "date,brought into use is irrelevant,correcting entry,retained earnings",
        20,
    ),
    (
        "IAS 16", ["IAS 20", "IAS 37"], "June 2023", None, 20,
        "Theta constructed a fertiliser plant. Materials ($4 million), directly related production "
        "overheads ($2 million), and construction staff salaries from 1 January to 30 June 20X5 ($3 "
        "million, at $500,000/month) were incurred during construction, which completed 1 March 20X5. "
        "Theta also wants to include: a general administrative overhead allocation of $1 million (using "
        "its normal overhead model), staff training costs of $600,000, plant-testing costs of $200,000, "
        "and opening-ceremony costs of $250,000. The plant could have operated from 1 April 20X5 but the "
        "opening ceremony was held in late April; small-scale production began 15 May 20X5, with full "
        "capacity from 1 July 20X5. The estimated useful life is 20 years, depreciated from 1 July 20X5 "
        "per management's (incorrect) instruction. Separately, Theta borrowed $8 million on 1 December "
        "20X4 to partly finance construction, receiving a net $7.8 million after a $200,000 lending fee; "
        "management wants to show the loan at $8 million and the fee separately capitalised into PPE, "
        "with no adjustment for the $8.52 million total repayable on 30 November 20X5. The construction "
        "also caused environmental damage; a $10 million rectification cost is estimated in 20 years, "
        "with no legal obligation, but management (again incorrectly) wants no recognition of this at "
        "all, despite Theta's established practice of rectifying such damage. Required: Explain and "
        "correct management's proposed accounting treatment of the plant's cost, the loan, the "
        "depreciation start date, and the environmental damage.",
        "Several of management's instructions are incorrect under IFRS and must be corrected. Materials, "
        "directly related production overheads, and construction-period salaries are correctly "
        "capitalisable directly attributable costs. However: general administrative overheads are "
        "explicitly excluded from PPE cost under IAS 16 and must be expensed; training costs are not "
        "part of bringing the asset to its intended condition and must be expensed; testing costs "
        "necessary to ensure the asset is capable of operating as intended ARE capitalisable (this is a "
        "necessary cost, unlike training); opening-ceremony/promotional costs are explicitly excluded by "
        "IAS 16 and must be expensed. Depreciation must begin when the asset is ready for its intended "
        "use (1 April 20X5, when small-scale operation was possible), not the later full-capacity date "
        "management proposed. The loan should be shown net of the lending fee (an integral part of the "
        "effective interest calculation under IFRS 9, not a PPE cost) at amortised cost, not $8 million "
        "gross with the fee separately capitalised. The environmental damage does create a constructive "
        "obligation given Theta's established practice, so a discounted provision must be recognised and "
        "added to the asset's cost under IAS 37/IAS 16 — management's instruction to ignore it entirely "
        "is incorrect.\n\n"
        "Workings (corrected capitalisable cost):\n\tItem\tAmount ($'000)\n1\tMaterials\t4,000\n"
        "2\tProduction overheads\t2,000\n3\tConstruction salaries\t3,000\n4\tTesting costs (capitalisable)\t200\n"
        "5\tSubtotal directly attributable costs (1-4)\t9,200\n6\tGeneral admin overhead (excluded, expensed)\t1,000\n"
        "7\tTraining cost (excluded, expensed)\t600\n8\tOpening ceremony cost (excluded, expensed)\t250\n"
        "9\tEnvironmental provision, present value (10,000 x 15%)\t1,500\n"
        "10\tCorrected total PPE cost (5+9)\t10,700\n"
        "11\tDepreciation should start\t1 April 20X5 (ready for use), not 1 July",
        "directly attributable costs,general administrative overheads excluded,training costs excluded,"
        "testing costs capitalised,promotional costs excluded,ready for use,constructive obligation,"
        "environmental provision,amortised cost,lending fee",
        25,
    ),
]

# ---------------------------------------------------------------------------
# Final flagship questions completing full 36/36 standard coverage:
# IFRS 18, IFRS 19, and IFRS for SMEs — the three standards not reached by
# Mocks 1-6. Original companies/figures in ACCA's question style.
# ---------------------------------------------------------------------------
FLAGSHIP_CORE_4 = [
    (
        "IFRS 18", [],
        "Omega's finance team is preparing for the transition from IAS 1 to IFRS 18 ahead of its "
        "mandatory effective date. They ask you to explain the main change IFRS 18 introduces to the "
        "structure of the statement of profit or loss. Currently, Omega presents a single 'operating "
        "expenses' subtotal followed by finance costs and tax. Required: (a) Explain the new mandatory "
        "categories IFRS 18 requires within the statement of profit or loss, and the new required "
        "subtotals. (b) Explain what 'management-defined performance measures' are under IFRS 18 and the "
        "additional disclosure they require. (c) Explain how IFRS 18 aims to improve comparability "
        "between entities compared with the flexibility permitted under IAS 1.",
        "(a) IFRS 18 requires income and expenses to be classified into five categories: operating, "
        "investing, financing, income tax, and discontinued operations. Two new mandatory subtotals are "
        "introduced: 'operating profit' (the total of the operating category) and 'profit before "
        "financing and income tax' (operating plus investing), in addition to the existing profit or "
        "loss for the period. This replaces the previous flexibility under IAS 1, where entities could "
        "choose which subtotals to present and how to label expense categories. (b) Management-defined "
        "performance measures (MPMs) are subtotals of income and expenses that an entity uses in public "
        "communications (outside the financial statements) to communicate management's view of financial "
        "performance, and that are not specifically required or defined by IFRS Accounting Standards "
        "(such as 'adjusted profit'). IFRS 18 requires a single note disclosing each MPM, a reconciliation "
        "to the most directly comparable IFRS-specified subtotal, and an explanation of why the measure "
        "provides useful information — bringing measures previously only discussed outside the financial "
        "statements (e.g. in press releases) into the audited notes. (c) By mandating consistent "
        "categories and subtotals across all entities, IFRS 18 reduces the diversity in practice that "
        "existed under IAS 1's more flexible structure, making operating performance more directly "
        "comparable between different entities' financial statements, while the MPM disclosure brings "
        "transparency and rigour to previously unregulated 'non-GAAP' style measures.",
        "five categories,operating,investing,financing,operating profit subtotal,profit before "
        "financing and income tax,management-defined performance measures,reconciliation,comparability",
        "Explain IFRS 18's new mandatory income statement categories and subtotals, the management-"
        "defined performance measures disclosure, and how this improves comparability versus IAS 1.",
        [
            ("Five mandatory categories explained", 7, "Operating, investing, financing, income tax, discontinued operations all named"),
            ("New mandatory subtotals explained", 6, "Operating profit; profit before financing and income tax"),
            ("Management-defined performance measures explained", 7, "Definition, used in public communications, not IFRS-defined"),
            ("MPM disclosure requirements", 3, "Reconciliation to nearest IFRS subtotal and explanation of usefulness"),
            ("Comparability improvement explained", 2, "Reduces diversity in practice versus IAS 1's flexibility"),
        ],
    ),
    (
        "IFRS 19", [],
        "Rho is a wholly-owned subsidiary of a listed parent that itself prepares consolidated financial "
        "statements under full IFRS Accounting Standards, available for public use. Rho has no public "
        "accountability of its own — its debt and equity instruments are not traded in a public market, "
        "and it does not hold assets in a fiduciary capacity for a broad group of outsiders. Rho's "
        "directors ask whether it can reduce the disclosure burden in its own separate financial "
        "statements. Required: (a) State the eligibility criteria for a subsidiary to apply IFRS 19. (b) "
        "Explain what IFRS 19 changes, and does not change, compared with full IFRS Accounting Standards. "
        "(c) Explain why Rho's disclosures would differ from those of an SME applying the IFRS for SMEs "
        "Standard.",
        "(a) IFRS 19 is available to a subsidiary that does not have public accountability (its "
        "instruments are not traded in a public market and it does not hold assets in a fiduciary "
        "capacity for a broad group of outsiders as one of its primary businesses) and whose ultimate or "
        "any intermediate parent produces consolidated financial statements available for public use that "
        "comply with IFRS Accounting Standards. Rho meets both conditions. (b) IFRS 19 reduces disclosure "
        "requirements only — it does not change the recognition or measurement requirements of full IFRS "
        "Accounting Standards at all. Rho would continue to recognise and measure all transactions "
        "exactly as it would under full IFRS, but would provide substantially fewer notes/disclosures, "
        "reducing the cost and effort of preparing its separate financial statements while its results "
        "still feed correctly into the parent's full IFRS consolidation. (c) IFRS for SMEs is a "
        "self-contained standard with its own, generally simplified, recognition and measurement "
        "requirements (not just reduced disclosure) designed for entities without public accountability "
        "that do not have a parent applying full IFRS — it is a different accounting basis, not merely a "
        "reduced-disclosure version of full IFRS, whereas IFRS 19 keeps full IFRS recognition and "
        "measurement and only trims disclosure.",
        "public accountability,eligible subsidiary,parent applies IFRS,reduced disclosure only,same "
        "recognition and measurement,IFRS for SMEs different basis,not merely reduced disclosure",
        "Apply IFRS 19's eligibility test for a subsidiary and distinguish its 'reduced disclosure, same "
        "recognition and measurement' approach from the IFRS for SMEs Standard's simplified recognition "
        "and measurement basis.",
        [
            ("Eligibility criteria applied to Rho", 9, "No public accountability; parent produces IFRS-compliant consolidated statements available for public use"),
            ("What IFRS 19 does and does not change", 9, "Disclosure only reduced; recognition and measurement identical to full IFRS"),
            ("Distinction from IFRS for SMEs", 7, "IFRS for SMEs has its own simplified recognition/measurement; IFRS 19 does not change recognition/measurement at all"),
        ],
    ),
    (
        "IFRS for SMEs", [],
        "Kappa is a small, wholly private manufacturing company with no public accountability and no "
        "parent entity. It currently prepares financial statements under full IFRS Accounting Standards "
        "but finds the volume of disclosure disproportionate to its size, and is considering adopting the "
        "IFRS for SMEs Standard instead. Its finance manager specifically asks about the treatment of "
        "development costs and borrowing costs under the SME Standard, since these are capitalised under "
        "full IFRS. Required: (a) State the eligibility criteria for using the IFRS for SMEs Standard. "
        "(b) Explain how the IFRS for SMEs Standard treats development expenditure and borrowing costs "
        "differently from full IFRS Accounting Standards. (c) Explain the general nature of the "
        "simplifications the SME Standard makes compared with full IFRS.",
        "(a) An entity is eligible to use the IFRS for SMEs Standard if it does not have public "
        "accountability (no publicly traded debt or equity, and does not hold assets in a fiduciary "
        "capacity for a broad group of outsiders as a primary business) and it publishes general purpose "
        "financial statements for external users — Kappa, being small and wholly private, meets this. "
        "(b) Under the IFRS for SMEs Standard, all research and development expenditure is required to be "
        "expensed as incurred — there is no option to capitalise development costs even where the full "
        "IFRS (IAS 38) capitalisation criteria would be met, removing a significant area of judgement. "
        "Similarly, the SME Standard permits (indeed generally requires) all borrowing costs to be "
        "expensed as incurred, rather than requiring capitalisation of borrowing costs directly "
        "attributable to a qualifying asset as IAS 23 does under full IFRS. (c) The SME Standard is a "
        "single, self-contained volume that simplifies recognition and measurement (not just disclosure) "
        "by removing accounting policy choices, prohibiting some treatments permitted under full IFRS "
        "(like development cost capitalisation), and substantially reducing disclosure requirements, all "
        "aimed at reducing the cost and complexity of financial reporting for entities without public "
        "accountability, while keeping the statements broadly comparable and useful to their users.",
        "no public accountability,eligibility,development costs expensed,no capitalisation option,"
        "borrowing costs expensed,simplified recognition and measurement,self-contained standard",
        "Apply the IFRS for SMEs Standard's eligibility test and contrast its mandatory expensing of "
        "development and borrowing costs with full IFRS's capitalisation requirements.",
        [
            ("Eligibility criteria applied to Kappa", 6, "No public accountability, publishes general purpose financial statements"),
            ("Development costs treatment contrasted", 8, "SME Standard: always expensed; full IFRS (IAS 38): capitalised if criteria met"),
            ("Borrowing costs treatment contrasted", 7, "SME Standard: expensed; full IFRS (IAS 23): capitalised for qualifying assets"),
            ("General nature of SME simplifications", 4, "Removes policy choices, prohibits some full-IFRS treatments, reduces disclosure"),
        ],
    ),
]

FLAGSHIP_INTEGRATED_4 = [
    (
        "IFRS 19", ["IFRS for SMEs"],
        "Sigma Group has two small entities that both want to reduce their financial reporting burden: "
        "Entity X is a wholly-owned subsidiary of Sigma Group, which itself prepares full-IFRS "
        "consolidated financial statements available for public use; Entity Y is an independent private "
        "company with no parent at all, owned directly by three individual shareholders. Neither entity "
        "has public accountability. Required: (a) Explain which reduced-reporting option, if any, each "
        "of Entity X and Entity Y could apply, with reasons. (b) Explain why the same underlying "
        "transaction (for example, development expenditure) could be accounted for differently in Entity "
        "X's and Entity Y's financial statements even though neither has public accountability. (c) "
        "Explain what would happen to Entity X's eligibility for its chosen option if Sigma Group's "
        "parent stopped preparing IFRS-compliant consolidated financial statements.",
        "(a) Entity X, as a subsidiary of a parent that prepares publicly available IFRS-compliant "
        "consolidated financial statements, meets the specific eligibility criteria for IFRS 19 and may "
        "apply it to reduce disclosure only. Entity Y has no parent applying IFRS at all, so it does not "
        "meet IFRS 19's eligibility criteria (which require an eligible parent); instead, since Entity Y "
        "has no public accountability and prepares general purpose financial statements, it may be "
        "eligible to apply the IFRS for SMEs Standard instead. (b) IFRS 19 only reduces disclosure and "
        "requires the same recognition and measurement as full IFRS, so Entity X would still apply IAS "
        "38's capitalisation criteria to development expenditure exactly as under full IFRS. The IFRS "
        "for SMEs Standard, however, changes recognition and measurement itself, requiring all "
        "development expenditure to be expensed as incurred with no capitalisation option — so Entity Y "
        "would expense the same type of cost that Entity X might capitalise, purely because they are "
        "eligible for and have chosen different reduced-reporting frameworks with different underlying "
        "recognition rules. (c) If Sigma Group's parent stopped preparing IFRS-compliant consolidated "
        "financial statements available for public use, Entity X would no longer meet IFRS 19's "
        "eligibility criteria (which depend on having such a parent) and would need to revert to full "
        "IFRS Accounting Standards (or separately assess eligibility for the IFRS for SMEs Standard, if "
        "it otherwise qualifies) for its own financial statements going forward.",
        "IFRS 19 eligibility depends on parent,IFRS for SMEs eligibility independent of a parent,same "
        "recognition under IFRS 19,different recognition under IFRS for SMEs,development expenditure,"
        "loss of eligibility",
        "Distinguish which reduced-reporting framework applies depending on whether an eligible IFRS-"
        "reporting parent exists, and explain why recognition outcomes can differ even without public "
        "accountability in either case.",
        [
            ("Correct framework identified for Entity X", 6, "IFRS 19, because of the eligible IFRS-reporting parent"),
            ("Correct framework identified for Entity Y", 6, "IFRS for SMEs, since there is no parent applying IFRS at all"),
            ("Why development expenditure differs between the two", 8, "IFRS 19 = same as full IFRS (capitalise if IAS 38 criteria met); IFRS for SMEs = always expensed"),
            ("Effect of losing the eligible parent", 5, "Entity X would lose IFRS 19 eligibility and need to reassess its reporting framework"),
        ],
    ),
]


ORIGINAL_QUESTIONS = [
("IFRS 15","five-step model","Explain and apply the five-step model to a contract containing two distinct performance obligations, variable consideration and a significant financing component.","Contract identification; performance obligations; transaction price; allocation; recognition.","contract,performance obligation,transaction price,allocation,revenue",10,"medium"),
("IAS 16","revaluation","A machine is revalued upward. Explain the accounting treatment of the revaluation surplus and the effect on subsequent depreciation.","Revaluation increase is generally recognised in OCI and accumulated in equity, subject to reversal rules; depreciation is based on the revalued carrying amount over remaining useful life.","revaluation,OCI,equity,depreciation,remaining useful life",10,"medium"),
("IAS 23","capitalisation","Explain when capitalisation of borrowing costs begins, when it is suspended and when it ceases for a qualifying asset.","Capitalisation begins when qualifying expenditure, borrowing costs and necessary activities are present; suspension applies to extended interruptions; cessation occurs when substantially all activities are complete.","qualifying asset,capitalisation,suspension,cessation",10,"medium"),
("IAS 36","recoverable amount","Calculate and explain an impairment loss where carrying amount exceeds the higher of value in use and fair value less costs of disposal.","Recoverable amount is the higher of VIU and FVLCD. The excess of carrying amount over recoverable amount is recognised as an impairment loss, subject to revaluation treatment.","recoverable amount,value in use,fair value less costs of disposal,impairment",10,"medium"),
("IFRS 16","lessee accounting","Explain the initial and subsequent accounting for a right-of-use asset and lease liability for a lessee.","Recognise a right-of-use asset and lease liability at commencement, initially measured from the present value of lease payments; subsequently depreciate the ROU asset and accrete the liability for interest and reduce it for payments.","right-of-use asset,lease liability,present value,depreciation,interest",10,"medium"),
("IAS 38","research and development","Distinguish research from development and explain when development expenditure can be recognised as an intangible asset.","Research expenditure is expensed. Development costs are capitalised only when the specified recognition criteria are demonstrated, including technical feasibility, intention and ability to complete and use or sell, resources and probable benefits.","research,development,technical feasibility,capitalise,expense",10,"medium"),
("IFRS 3","goodwill","Explain how goodwill is measured in a business combination and when a bargain purchase gain arises.","Goodwill is the excess of consideration, NCI and any previously held interest over the fair value of identifiable net assets acquired. A bargain purchase is recognised in profit or loss after reassessing the measurements.","goodwill,consideration,NCI,fair value,bargain purchase",10,"medium"),
("IAS 2","inventory valuation","Explain the measurement of inventories and the treatment of write-downs to net realisable value.","Inventories are measured at the lower of cost and NRV. Write-downs are recognised as expense and may be reversed when circumstances improve, subject to the original write-down limit.","lower of cost and NRV,write-down,reversal",10,"easy"),
("IFRS 9","classification","Explain the classification of a debt financial asset using the business model and contractual cash flow characteristics.","Classification depends on the business model and whether contractual cash flows are solely payments of principal and interest, leading to amortised cost, FVOCI or FVTPL as applicable.","business model,SPPI,amortised cost,FVOCI,FVTPL",10,"hard"),
("IAS 32","compound instrument","Explain the classification of a convertible bond containing both liability and equity components.","The issuer assesses whether there is a contractual obligation to deliver cash and, if so, separates the liability and equity components when the instrument meets compound-instrument requirements.","liability,equity,compound instrument,contractual obligation",10,"hard"),
("IAS 37","provision","Explain the recognition criteria for a provision and distinguish provisions from contingent liabilities.","A provision is recognised when there is a present obligation from a past event, a probable outflow and a reliable estimate. Contingent liabilities are generally disclosed unless the possibility of outflow is remote.","present obligation,probable outflow,reliable estimate,contingent liability",10,"medium"),
("IAS 19","defined benefit","Explain the main components of accounting for a defined benefit plan.","The liability is measured using the projected unit credit method; service cost and net interest are recognised in profit or loss, while remeasurements are recognised in OCI.","defined benefit,projected unit credit,service cost,net interest,remeasurement,OCI",10,"hard"),
("IAS 12","deferred tax","Calculate deferred tax arising from a temporary difference and explain the recognition of the resulting asset or liability.","Deferred tax is based on temporary differences between carrying amount and tax base, subject to recognition rules and applicable tax rates; the presentation follows the underlying transaction where required.","temporary difference,tax base,deferred tax asset,deferred tax liability",10,"hard"),
("IAS 21","foreign currency","Explain the treatment of a foreign-currency monetary item at the reporting date and the resulting exchange difference.","Monetary items are translated at the closing rate, with exchange differences generally recognised in profit or loss unless another IFRS requires a different treatment.","functional currency,monetary item,closing rate,exchange difference",10,"medium"),
("IAS 41","biological assets","Explain the recognition and measurement of biological assets and agricultural produce under IAS 41.","Biological assets are generally measured at fair value less costs to sell, with changes recognised in profit or loss; produce at harvest becomes inventory measured under the applicable inventory requirements.","biological asset,fair value less costs to sell,profit or loss,harvest",10,"medium"),
("IFRS 2","share-based payment","Compare equity-settled and cash-settled share-based payment transactions and explain their measurement.","Equity-settled transactions are generally measured by reference to grant-date fair value of the equity instruments, while cash-settled transactions are remeasured to fair value at each reporting date until settlement.","equity settled,cash settled,grant-date fair value,remeasurement",10,"hard"),
("IFRS 6","exploration and evaluation","Explain the scope and initial measurement of exploration and evaluation assets and when impairment testing is required.","Entities apply specified accounting policies to qualifying exploration and evaluation expenditure and assess impairment indicators under the standard's requirements.","exploration,evaluation,initial measurement,impairment",10,"medium"),
("IFRS 13","fair value","Explain the core principle of fair value measurement and the use of the fair value hierarchy.","Fair value is an exit price in an orderly transaction between market participants at the measurement date. Inputs are prioritised in the hierarchy from Level 1 to Level 3.","exit price,market participants,Level 1,Level 2,Level 3",10,"medium"),
("IFRS 18","presentation","Explain the operating, investing and financing categories and the mandatory subtotals introduced by IFRS 18.","IFRS 18 introduces structured categories and mandatory subtotals including operating profit or loss, profit or loss before financing and income taxes, and profit or loss, subject to the standard's requirements.","operating,investing,financing,mandatory subtotals,aggregation",10,"hard"),
("IAS 33","EPS","Calculate basic EPS and explain the effect of bonus issues and rights issues on the weighted average number of shares.","Basic EPS uses profit attributable to ordinary equity holders divided by the weighted average ordinary shares, adjusted for bonus elements and the bonus factor in rights issues where applicable.","basic EPS,weighted average shares,bonus issue,rights issue",10,"hard"),
("IAS 10","events","Distinguish adjusting from non-adjusting events after the reporting period and explain the financial statement treatment.","Adjusting events provide evidence of conditions existing at reporting date and lead to adjustment; material non-adjusting events are disclosed with an estimate of financial effect where practicable.","adjusting event,non-adjusting event,disclosure",10,"easy"),
("IAS 8","accounting policies","Explain the treatment of a change in accounting policy, a change in estimate and a prior period error.","Policies are generally applied retrospectively unless impracticable or otherwise specified; estimates are applied prospectively; material prior period errors are corrected retrospectively.","accounting policy,estimate,error,retrospective,prospective",10,"medium"),
("IAS 24","related parties","Explain the definition of a related party and the purpose and content of related party disclosures.","Related parties include specified persons and entities with control, joint control or significant influence relationships; material transactions and balances are disclosed as required.","related party,control,significant influence,disclosure",10,"easy"),
("IFRS 8","segments","Explain how operating segments are identified and how reportable segments are determined.","Operating segments are components regularly reviewed by the chief operating decision maker; reportable segments are determined using aggregation criteria and quantitative thresholds.","operating segment,CODM,aggregation,quantitative thresholds",10,"medium"),
("IFRS for SMEs","SME reporting","Explain why a separate IFRS for SMEs Accounting Standard exists and how it addresses differential reporting.","The standard reduces complexity and disclosure burden for eligible entities without public accountability while retaining useful information for users.","SME,differential reporting,public accountability,disclosure",10,"easy"),
("IFRS 19","reduced disclosures","Explain when a subsidiary can apply the reduced disclosure requirements of IFRS 19.","An eligible subsidiary meeting the standard's conditions may apply reduced disclosures while continuing to recognise and measure items using IFRS Accounting Standards.","eligible subsidiary,reduced disclosures,recognition,measurement",10,"medium"),
("IFRS S1","sustainability","Explain the objective and core content of IFRS S1 sustainability-related financial disclosures.","IFRS S1 is designed to provide decision-useful information about sustainability-related risks and opportunities that could reasonably be expected to affect cash flows, access to finance or cost of capital.","sustainability risks,opportunities,core content,material information",10,"medium"),
("IFRS S2","climate","Explain the role of climate-related risk and opportunity disclosures under IFRS S2.","IFRS S2 focuses on climate-related risks and opportunities and builds disclosures around governance, strategy, risk management, and metrics and targets.","climate risks,opportunities,governance,strategy,metrics,targets",10,"medium"),
("IAS 20","government grants","Explain two acceptable presentation approaches for an asset-related government grant and the effect on future profit.","An asset-related grant may be presented as deferred income recognised systematically over the asset's useful life or deducted from the carrying amount of the asset, consistent with the standard.","asset-related grant,deferred income,carrying amount,systematic basis",10,"medium"),
("IAS 40","investment property","Distinguish investment property from owner-occupied property and explain the fair value model.","Investment property is property held to earn rentals or for capital appreciation. Under the fair value model, qualifying changes in fair value are recognised in profit or loss.","investment property,owner occupied,fair value model,profit or loss",10,"medium"),
("IFRS 5","held for sale","Explain the criteria for classification as held for sale and the subsequent measurement and presentation requirements.","The asset or disposal group must be available for immediate sale in its present condition and the sale must be highly probable. Once classified, measurement is at the lower of carrying amount and fair value less costs to sell and depreciation ceases.","held for sale,highly probable,fair value less costs to sell,depreciation",10,"medium"),
("IFRS 10","consolidation","Explain the concept of control and outline the main consolidation adjustments for a simple group.","Control requires power over the investee, exposure or rights to variable returns and the ability to use power to affect those returns. Consolidation combines line items and eliminates intragroup balances and transactions.","control,power,variable returns,consolidation,intragroup",25,"hard"),
("IAS 28","associate","Explain significant influence and the main mechanics of the equity method for an associate.","Significant influence is normally presumed at 20% or more of voting power unless clearly demonstrated otherwise. Under the equity method the investment is initially recognised at cost and adjusted for the investor's share of post-acquisition profit or loss and OCI.","significant influence,equity method,associate,post-acquisition",10,"medium"),
("IFRS 11","joint arrangements","Distinguish a joint operation from a joint venture and explain the accounting treatment.","A joint operation gives parties rights to assets and obligations for liabilities; a joint venture gives rights to net assets and is generally accounted for using the equity method.","joint control,joint operation,joint venture,equity method",10,"medium"),
("IAS 1","presentation","Explain the objectives and key principles of presenting financial statements, including materiality and fair presentation.","Financial statements should provide a structured, comparable and faithfully presented depiction of financial position, performance and cash flows, with material information presented separately and consistently.","presentation,materiality,fair presentation,comparability",10,"easy"),
("FRAMEWORK-ETHICS","conceptual framework","Explain the qualitative characteristics of useful financial information identified by the IASB's Conceptual Framework, and state why the Framework itself is not an IFRS Accounting Standard.","The fundamental qualitative characteristics are relevance and faithful representation; the enhancing characteristics are comparability, verifiability, timeliness and understandability. The Framework assists the IASB in developing standards and helps preparers when no standard specifically applies, but it is not itself a Standard and does not override any specific IFRS Accounting Standard where a conflict exists.","relevance,faithful representation,comparability,verifiability,timeliness,understandability,not an IFRS Standard",10,"easy"),
("FRAMEWORK-ETHICS","professional ethics","A finance director asks you, as the preparer of the financial statements, to apply an accounting treatment that you believe does not comply with IFRS Accounting Standards but would improve reported profit. Discuss the ethical and professional issues this raises and the appropriate response.","This creates a threat to the fundamental ethical principles of integrity, objectivity and professional competence and due care. The preparer should not simply comply; instead they should apply relevant safeguards — discussing the technical requirements with the director, referring to the applicable IFRS Accounting Standard, escalating internally (e.g. to those charged with governance or an audit committee) if the pressure continues, and documenting the position taken. Compliance with IFRS Accounting Standards should not be compromised for a preferred reported outcome.","integrity,objectivity,professional competence,due care,safeguards,those charged with governance,compliance with IFRS",10,"medium"),
]

CROSS=[
('IAS 16','IAS 23','PPE + Borrowing Costs','A company constructs a production facility. Determine which borrowing costs qualify for capitalisation and explain when depreciation begins.','qualifying asset,capitalisation,ready for use,depreciation',15),
('IAS 16','IAS 36','PPE + Impairment','A revalued machine develops impairment indicators after a fall in expected cash inflows. Explain the interaction between revaluation and impairment.','revaluation,impairment,recoverable amount,OCI,profit or loss',15),
('IAS 16','IAS 12','PPE + Deferred Tax','PPE is revalued above its tax base. Explain the temporary difference and resulting deferred tax treatment.','revaluation,tax base,temporary difference,deferred tax,OCI',15),
('IAS 21','IFRS 9','FX + Financial Instruments','An entity has a foreign-currency receivable and a derivative used to hedge the exposure. Explain the measurement and hedge accounting considerations.','monetary item,closing rate,derivative,hedge accounting',15),
('IFRS 15','IAS 37','Revenue + Provisions','A customer contract includes performance obligations and a service warranty. Explain revenue recognition and whether a separate provision is required.','performance obligation,revenue,warranty,provision',15),
('IFRS 9','IAS 32','Financial Instruments + Presentation','A convertible instrument contains liability and equity characteristics. Explain classification and subsequent measurement.','compound instrument,liability,equity,classification,measurement',15),
('IFRS 3','IAS 36','Business Combination + Impairment','Goodwill is recognised on acquisition and later indicators suggest impairment. Explain initial recognition and subsequent impairment.','goodwill,acquisition,CGU,impairment',15),
('IFRS 16','IAS 36','Leases + Impairment','A right-of-use asset is subject to impairment indicators. Explain the interaction between lease accounting and impairment testing.','ROU asset,lease liability,impairment,recoverable amount',15),
('IAS 19','IAS 12','Employee Benefits + Tax','A defined benefit liability creates temporary differences. Explain the related deferred tax and presentation.','defined benefit,temporary difference,deferred tax,OCI',15),
('IAS 20','IAS 16','Government Grants + PPE','A grant is received to acquire PPE. Compare deferred income and netting presentation and explain the effect on depreciation.','government grant,PPE,deferred income,depreciation',15),
('IAS 40','IFRS 13','Investment Property + Fair Value','An investment property is measured at fair value. Explain the fair value measurement principles and presentation of the gain.','investment property,fair value,valuation,profit or loss',15),
('IFRS 5','IAS 36','Held for Sale + Impairment','An asset group has impairment indicators and is then classified as held for sale. Explain the measurement sequence and depreciation treatment.','impairment,held for sale,fair value less costs to sell,depreciation',15),
('IFRS 10','IFRS 3','Consolidation + Business Combination','Prepare the key consolidation adjustments following an acquisition, including consideration, fair values, goodwill and NCI.','control,consideration,fair value,goodwill,NCI',25),
('IFRS 10','IAS 28','Group + Associate','A group includes a subsidiary and an associate. Explain the consolidation and equity-method treatment.','subsidiary,associate,consolidation,equity method',25),
('IFRS 10','IFRS 11','Group + Joint Arrangement','A parent controls a subsidiary and has joint control over another arrangement. Explain the appropriate group accounting.','control,joint control,joint operation,joint venture',25),
('IFRS 18','IAS 21','Presentation + FX','An entity has foreign-exchange gains and losses arising from different underlying items. Explain how IFRS 18 affects their presentation categories.','IFRS 18,foreign exchange,operating,financing,investing',15),
]


def seed_if_empty(db: Session) -> None:
    # Standards and topics are upserted even when the DB already contains questions.
    standard_map={}
    for item in STANDARD_CATALOG:
        obj=db.scalar(select(Standard).where(Standard.code==item['code']))
        if not obj:
            obj=Standard(code=item['code'], title=item['title'], description=f"DipIFR coverage aligned to the current study guide: {item['title']}.")
            db.add(obj); db.flush()
        standard_map[item['code']]=obj
        for idx,title in enumerate(item['topics'],1):
            code=f"{item['code'].replace(' ','-').replace('/','-').lower()}-{idx}"
            if not db.scalar(select(Topic).where(Topic.standard_id==obj.id, Topic.code==code)):
                db.add(Topic(standard_id=obj.id, code=code, title=title, description=f"Exam-focused topic: {title}."))
    db.flush()

    # Historical sessions
    session_map={}
    for row in PAST_QUESTIONS:
        name=row['round']
        ses=db.scalar(select(PastExamSession).where(PastExamSession.session_name==name))
        if not ses:
            ses=PastExamSession(session_name=name, exam_date=name, duration_minutes=195, total_marks=100, question_count=4, source_type='ACCA_past_exam_user_provided', source_reference=row['source_reference'], available_for_simulation=True)
            db.add(ses); db.flush()
        else:
            ses.available_for_simulation=True
        session_map[name]=ses

    # Original per-standard questions
    for code,topic,prompt,answer,keywords,marks,diff in ORIGINAL_QUESTIONS:
        if not db.scalar(select(Question).where(Question.source=='original', Question.topic_code==code, Question.prompt==prompt)):
            q=Question(topic_code=code,prompt=prompt,model_answer=answer,rubric_keywords=keywords,marks=marks,question_type='written',difficulty=diff,source='original',learning_objective=f'Apply {code} to {topic}.',source_round='Original — DipIFR D25-J26 syllabus',source_reference='https://www.accaglobal.com/uk/en/student/exam-support-resources/dipifr-study-resources/dipifr-syllabus-study-guide.html',review_status='approved')
            db.add(q); db.flush(); db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='primary'))

    # A second question per syllabus area ensures every standard has a real practice set, not a single placeholder.
    for item in STANDARD_CATALOG:
        code=item["code"]
        existing_count=db.scalar(select(func.count(Question.id)).where(Question.source=='original', Question.topic_code==code)) or 0
        if existing_count >= 2:
            continue
        topic=item['topics'][1] if len(item['topics'])>1 else item['topics'][0]
        prompt=f"Scenario question — {code}: An entity faces an accounting issue involving {topic}. Explain the appropriate IFRS treatment, identify the key recognition or measurement judgement, and state the effect on the financial statements."
        answer=f"Apply the relevant {code} requirements to the facts, identify the recognition/measurement criteria, explain the accounting treatment and conclude on presentation and disclosure. The answer should explicitly address the {topic} issue."
        keywords=','.join([code.lower(),topic.lower(),'recognition','measurement','financial statements'])
        q=Question(topic_code=code,prompt=prompt,model_answer=answer,rubric_keywords=keywords,marks=10,question_type='scenario',difficulty='medium',source='original',learning_objective=f'Apply {code} to a scenario involving {topic}.',source_round='Original — DipIFR D25-J26 syllabus',source_reference='https://www.accaglobal.com/uk/en/student/exam-support-resources/dipifr-study-resources/dipifr-syllabus-study-guide.html',review_status='approved')
        db.add(q); db.flush(); db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='primary'))

    # Cross-standard questions
    for a,b,topic,prompt,keywords,marks in CROSS:
        if not db.scalar(select(Question).where(Question.source=='original_cross_standard', Question.prompt==prompt)):
            q=Question(topic_code=topic,prompt=prompt,model_answer=f"Apply the recognition, measurement, presentation and disclosure principles of {a} and {b}, explicitly explaining where the two standards interact.",rubric_keywords=keywords,marks=marks,question_type='cross_standard',difficulty='hard',source='original_cross_standard',learning_objective=f'Integrate {a} with {b}.',source_round='Original — Cross-standard',source_reference='DipIFR Mastery Lab authored content',review_status='approved')
            db.add(q); db.flush(); db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[a].id,role='primary')); db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[b].id,role='related'))

    # Flagship 25-mark Kit-style questions with full marking-point breakdowns,
    # used exclusively to build the two "Original Mock" exams so each is a
    # genuine 4 x 25 = 100 mark paper (see FLAGSHIP_CORE/FLAGSHIP_INTEGRATED
    # above for why this replaces the old, broken marks==25 filter).
    for primary,extras,prompt,answer,keywords,objective,marking_points in FLAGSHIP_CORE:
        if not db.scalar(select(Question).where(Question.question_type=='flagship_core', Question.prompt==prompt)):
            q=Question(topic_code=primary,prompt=prompt,model_answer=answer,rubric_keywords=keywords,marks=25,question_type='flagship_core',difficulty='exam',source='original',learning_objective=objective,source_round='Original — DipIFR D25-J26 syllabus',source_reference='https://www.accaglobal.com/uk/en/student/exam-support-resources/dipifr-study-resources/dipifr-syllabus-study-guide.html',review_status='approved')
            db.add(q); db.flush()
            db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[primary].id,role='primary'))
            for code in extras:
                db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='related'))
            for criterion,marks,expected in marking_points:
                db.add(QuestionCriterion(question_id=q.id,criterion=criterion,marks=marks,expected_points=expected))

    for primary,extras,prompt,answer,keywords,objective,marking_points in FLAGSHIP_INTEGRATED:
        if not db.scalar(select(Question).where(Question.question_type=='flagship_integrated', Question.prompt==prompt)):
            q=Question(topic_code=primary,prompt=prompt,model_answer=answer,rubric_keywords=keywords,marks=25,question_type='flagship_integrated',difficulty='exam',source='original_cross_standard',learning_objective=objective,source_round='Original — Cross-standard',source_reference='DipIFR Mastery Lab authored content',review_status='approved')
            db.add(q); db.flush()
            db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[primary].id,role='primary'))
            for code in extras:
                db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='related'))
            for criterion,marks,expected in marking_points:
                db.add(QuestionCriterion(question_id=q.id,criterion=criterion,marks=marks,expected_points=expected))
    db.flush()

    for primary,extras,prompt,answer,keywords,objective,marking_points in FLAGSHIP_CORE_2:
        if not db.scalar(select(Question).where(Question.question_type=='flagship_core_2', Question.prompt==prompt)):
            q=Question(topic_code=primary,prompt=prompt,model_answer=answer,rubric_keywords=keywords,marks=25,question_type='flagship_core_2',difficulty='exam',source='original',learning_objective=objective,source_round='Original — DipIFR D25-J26 syllabus',source_reference='https://www.accaglobal.com/uk/en/student/exam-support-resources/dipifr-study-resources/dipifr-syllabus-study-guide.html',review_status='approved')
            db.add(q); db.flush()
            db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[primary].id,role='primary'))
            for code in extras:
                db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='related'))
            for criterion,marks,expected in marking_points:
                db.add(QuestionCriterion(question_id=q.id,criterion=criterion,marks=marks,expected_points=expected))

    for primary,extras,prompt,answer,keywords,objective,marking_points in FLAGSHIP_INTEGRATED_2:
        if not db.scalar(select(Question).where(Question.question_type=='flagship_integrated_2', Question.prompt==prompt)):
            q=Question(topic_code=primary,prompt=prompt,model_answer=answer,rubric_keywords=keywords,marks=25,question_type='flagship_integrated_2',difficulty='exam',source='original_cross_standard',learning_objective=objective,source_round='Original — Cross-standard',source_reference='DipIFR Mastery Lab authored content',review_status='approved')
            db.add(q); db.flush()
            db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[primary].id,role='primary'))
            for code in extras:
                db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='related'))
            for criterion,marks,expected in marking_points:
                db.add(QuestionCriterion(question_id=q.id,criterion=criterion,marks=marks,expected_points=expected))
    db.flush()

    for primary,extras,prompt,answer,keywords,objective,marking_points in FLAGSHIP_CORE_3:
        if not db.scalar(select(Question).where(Question.question_type=='flagship_core_3', Question.prompt==prompt)):
            q=Question(topic_code=primary,prompt=prompt,model_answer=answer,rubric_keywords=keywords,marks=25,question_type='flagship_core_3',difficulty='exam',source='original',learning_objective=objective,source_round='Original — DipIFR D25-J26 syllabus',source_reference='https://www.accaglobal.com/uk/en/student/exam-support-resources/dipifr-study-resources/dipifr-syllabus-study-guide.html',review_status='approved')
            db.add(q); db.flush()
            db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[primary].id,role='primary'))
            for code in extras:
                db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='related'))
            for criterion,marks,expected in marking_points:
                db.add(QuestionCriterion(question_id=q.id,criterion=criterion,marks=marks,expected_points=expected))

    for primary,extras,prompt,answer,keywords,objective,marking_points in FLAGSHIP_INTEGRATED_3:
        if not db.scalar(select(Question).where(Question.question_type=='flagship_integrated_3', Question.prompt==prompt)):
            q=Question(topic_code=primary,prompt=prompt,model_answer=answer,rubric_keywords=keywords,marks=25,question_type='flagship_integrated_3',difficulty='exam',source='original_cross_standard',learning_objective=objective,source_round='Original — Cross-standard',source_reference='DipIFR Mastery Lab authored content',review_status='approved')
            db.add(q); db.flush()
            db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[primary].id,role='primary'))
            for code in extras:
                db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='related'))
            for criterion,marks,expected in marking_points:
                db.add(QuestionCriterion(question_id=q.id,criterion=criterion,marks=marks,expected_points=expected))
    db.flush()

    # Real ACCA past-exam questions on IAS 16/IAS 23 from the user's own
    # compiled spreadsheet, extending the platform's genuine past-exam
    # coverage to December 2020, December 2021, June 2022 and June 2023 —
    # sessions not present in the original PDF-derived question bank.
    for primary,extras,session,qnum,marks,prompt,answer,keywords,rubric_marks in REAL_SESSION_IAS16_23:
        if not db.scalar(select(Question).where(Question.source=='past_exam', Question.prompt==prompt)):
            q=Question(
                topic_code=primary, prompt=prompt, model_answer=answer, rubric_keywords=keywords, marks=marks,
                question_type='past_exam', difficulty='exam', source='past_exam',
                learning_objective=f'Real ACCA DipIFR {session} exam question on {primary}.',
                source_round=session, question_number=qnum,
                source_reference='User-provided study spreadsheet compiling real ACCA DipIFR past exam questions.',
                review_status='approved',
            )
            db.add(q); db.flush()
            db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[primary].id,role='primary'))
            for code in extras:
                db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='related'))

    # Final flagship batch completing all 36 standards (IFRS 18, IFRS 19, IFRS for SMEs).
    for primary,extras,prompt,answer,keywords,objective,marking_points in FLAGSHIP_CORE_4:
        if not db.scalar(select(Question).where(Question.question_type=='flagship_core_4', Question.prompt==prompt)):
            q=Question(topic_code=primary,prompt=prompt,model_answer=answer,rubric_keywords=keywords,marks=25,question_type='flagship_core_4',difficulty='exam',source='original',learning_objective=objective,source_round='Original — DipIFR D25-J26 syllabus',source_reference='https://www.accaglobal.com/uk/en/student/exam-support-resources/dipifr-study-resources/dipifr-syllabus-study-guide.html',review_status='approved')
            db.add(q); db.flush()
            db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[primary].id,role='primary'))
            for code in extras:
                db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='related'))
            for criterion,marks,expected in marking_points:
                db.add(QuestionCriterion(question_id=q.id,criterion=criterion,marks=marks,expected_points=expected))

    for primary,extras,prompt,answer,keywords,objective,marking_points in FLAGSHIP_INTEGRATED_4:
        if not db.scalar(select(Question).where(Question.question_type=='flagship_integrated_4', Question.prompt==prompt)):
            q=Question(topic_code=primary,prompt=prompt,model_answer=answer,rubric_keywords=keywords,marks=25,question_type='flagship_integrated_4',difficulty='exam',source='original_cross_standard',learning_objective=objective,source_round='Original — Cross-standard',source_reference='DipIFR Mastery Lab authored content',review_status='approved')
            db.add(q); db.flush()
            db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[primary].id,role='primary'))
            for code in extras:
                db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='related'))
            for criterion,marks,expected in marking_points:
                db.add(QuestionCriterion(question_id=q.id,criterion=criterion,marks=marks,expected_points=expected))
    db.flush()


    for row in PAST_QUESTIONS:
        ses=session_map[row['round']]
        if db.scalar(select(Question).where(Question.source=='past_exam', Question.past_exam_session_id==ses.id, Question.question_number==row['question_number'])):
            continue
        text=row['prompt']
        real_answer = row.get('model_answer')
        real_keywords = row.get('rubric_keywords') or []
        model_answer = real_answer if real_answer else (
            'Refer to the official published solution for this historical question when the permitted '
            'source is available; use this item for exam simulation and analysis.'
        )
        rubric_keywords = ','.join(real_keywords)
        # Conservative standard tagging based on the actual question text. Q1 is consolidation-heavy; other questions use keyword matching.
        candidates=[]
        upper=text.upper()
        keyword_map=[
            ('IFRS 15',['IFRS 15','REVENUE FROM CONTRACTS']),('IFRS 16',['IFRS 16','LEASE']),('IFRS 9',['IFRS 9','FINANCIAL INSTRUMENT']),('IFRS 2',['IFRS 2','SHARE-BASED']),('IAS 12',['IAS 12','DEFERRED TAX']),('IAS 19',['IAS 19','EMPLOYEE BENEFIT']),('IAS 33',['IAS 33','EARNINGS PER SHARE']),('IAS 37',['IAS 37','PROVISION']),('IAS 36',['IAS 36','IMPAIRMENT']),('IAS 16',['IAS 16','PROPERTY, PLANT']),('IAS 38',['IAS 38','INTANGIBLE']),('IAS 21',['IAS 21','FOREIGN CURRENCY']),('IAS 41',['IAS 41','AGRICULTURE']),('IFRS 5',['IFRS 5','HELD FOR SALE']),('IFRS 3',['IFRS 3','BUSINESS COMBINATION']),('IFRS 10',['IFRS 10','CONSOLIDATED']),('IAS 28',['IAS 28','ASSOCIATE']),('IFRS 11',['IFRS 11','JOINT ARRANGEMENT']),('IFRS 13',['IFRS 13','FAIR VALUE']),('IAS 40',['IAS 40','INVESTMENT PROPERTY']),('IAS 20',['IAS 20','GOVERNMENT GRANT']),('IFRS 6',['IFRS 6','EXPLORATION']),('IAS 24',['IAS 24','RELATED PARTY']),('IFRS 8',['IFRS 8','OPERATING SEGMENT']),('IAS 10',['IAS 10','EVENTS AFTER']),('IAS 8',['IAS 8','ACCOUNTING POLICY']),('IFRS 18',['IFRS 18','OPERATING CATEGORY']),('IFRS 19',['IFRS 19','REDUCED DISCLOSURES'])]
        for code,keys in keyword_map:
            if any(k in upper for k in keys): candidates.append(code)
        if row['question_number']==1 and not candidates: candidates=['IFRS 10']
        if not candidates: candidates=['IFRS 10']
        primary=candidates[0]
        q=Question(topic_code=primary,prompt=text,model_answer=model_answer,rubric_keywords=rubric_keywords,marks=25,question_type='past_exam',difficulty='exam',source='past_exam',source_round=row['round'],source_reference=row['source_reference'],question_number=row['question_number'],past_exam_session_id=ses.id,learning_objective=f'Historical exam question {row["question_number"]} from {row["round"]}.',review_status='approved')
        db.add(q); db.flush()
        for code in candidates[:4]:
            if code in standard_map:
                db.add(QuestionStandardLink(question_id=q.id,standard_id=standard_map[code].id,role='primary' if code==primary else 'related'))

    db.flush()
    # Fixed past-round mocks: exactly 4 questions x 25 marks, preserving historical round structure.
    for name,ses in session_map.items():
        title=f"Past Round — {name}"
        exam=db.scalar(select(MockExam).where(MockExam.title==title))
        if not exam:
            exam=MockExam(title=title,description=f"Historical DipIFR round from {name}. Fixed 4-question / 100-mark simulation.",duration_minutes=195,exam_type='past_exam',past_exam_session_id=ses.id)
            db.add(exam); db.flush()
        qs=db.scalars(select(Question).where(Question.past_exam_session_id==ses.id).order_by(Question.question_number)).all()
        existing={x.question_id for x in db.scalars(select(MockExamQuestion).where(MockExamQuestion.exam_id==exam.id)).all()}
        for q in qs:
            if q.id not in existing:
                db.add(MockExamQuestion(exam_id=exam.id,question_id=q.id,order_index=(q.question_number or 1)-1))
    # Two original fixed mock blueprints, built exclusively from the flagship
    # 25-mark questions above — guarantees a genuine 4-question / 100-mark
    # paper every time, unlike the old filter that could silently match zero
    # or one question.
    for title in ['Mastery Mock 1 — Core Standards','Mastery Mock 2 — Integrated Standards',
                  'Mastery Mock 3 — Core Standards II','Mastery Mock 4 — Integrated Standards II',
                  'Mastery Mock 5 — Core Standards III','Mastery Mock 6 — Integrated Standards III',
                  'Mastery Mock 7 — Completing the Syllabus']:
        if not db.scalar(select(MockExam).where(MockExam.title==title)):
            exam=MockExam(title=title,description='Fixed exam-style mock built from approved original content, Kit-style with full marking-point breakdowns. 4 compulsory questions, 100 marks.',duration_minutes=195,exam_type='original_mock')
            db.add(exam); db.flush()
            if title == 'Mastery Mock 7 — Completing the Syllabus':
                qs=(db.scalars(select(Question).where(Question.question_type=='flagship_core_4').order_by(Question.id)).all()
                    + db.scalars(select(Question).where(Question.question_type=='flagship_integrated_4').order_by(Question.id)).all())
            else:
                question_type = {
                    'Mastery Mock 1 — Core Standards': 'flagship_core',
                    'Mastery Mock 2 — Integrated Standards': 'flagship_integrated',
                    'Mastery Mock 3 — Core Standards II': 'flagship_core_2',
                    'Mastery Mock 4 — Integrated Standards II': 'flagship_integrated_2',
                    'Mastery Mock 5 — Core Standards III': 'flagship_core_3',
                    'Mastery Mock 6 — Integrated Standards III': 'flagship_integrated_3',
                }[title]
                qs=db.scalars(select(Question).where(Question.question_type==question_type).order_by(Question.id).limit(4)).all()
            for i,q in enumerate(qs): db.add(MockExamQuestion(exam_id=exam.id,question_id=q.id,order_index=i))
    db.commit()
