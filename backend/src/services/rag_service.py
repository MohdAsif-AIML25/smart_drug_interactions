"""
RAG Service — Retrieval-Augmented Generation

Pipeline:
  1. Fetch real-time data from RxNorm (NIH) + OpenFDA Label API
  2. Store new findings in ChromaDB (auto-expanding knowledge base)
  3. Retrieve semantically relevant documents from ChromaDB
  4. Stream explanation from Groq LLM token by token

Real-time APIs used (both free, no API key required):
  - RxNorm Drug Interaction API: https://rxnav.nlm.nih.gov/REST/
  - OpenFDA Drug Label API:      https://api.fda.gov/drug/label.json
"""

import asyncio
import hashlib
from typing import AsyncGenerator, List, Optional

import httpx
import chromadb
from chromadb.utils import embedding_functions
from groq import AsyncGroq

from src.core.config import settings
from src.core.logger import logger

# ── Real-time API base URLs ──────────────────────────────────────
RXNORM_BASE   = "https://rxnav.nlm.nih.gov/REST"
OPENFDA_BASE  = "https://api.fda.gov/drug"
from src.models.schemas import DrugSource


SYSTEM_PROMPT = """You are a clinical pharmacology AI assistant.
Your role is to explain drug-drug interactions clearly and accurately.

Guidelines:
- Use plain language suitable for patients and caregivers
- Always mention the clinical significance (what symptoms/risks to watch for)
- Suggest monitoring recommendations
- Be precise but compassionate
- Keep explanations between 150-250 words
- Never provide dosing advice
- Always recommend consulting a healthcare provider
"""

# ══════════════════════════════════════════════════════════════════
# COMPLETE CHROMADB SEED DATA — All severity levels
# 30+ drug pairs from the interaction knowledge base
# ══════════════════════════════════════════════════════════════════

SEED_DATA = [

    # ── CRITICAL PAIRS ─────────────────────────────────────────────
    {
        "id": "warfarin_aspirin_1",
        "text": "Warfarin and Aspirin critical interaction: Co-administration significantly increases bleeding risk. Aspirin inhibits platelet aggregation while warfarin inhibits vitamin K-dependent clotting factors. Together they impair two separate pathways of hemostasis. Risk of GI bleeding and intracranial hemorrhage is elevated. Monitor INR closely. Symptoms: unusual bruising, black/tarry stools, prolonged bleeding from cuts.",
        "source": "openfda", "drug_pair": "warfarin_aspirin", "severity": "contraindicated",
    },
    {
        "id": "nitroglycerin_sildenafil_1",
        "text": "Nitroglycerin and Sildenafil dangerous hypotension: Both drugs cause vasodilation by different mechanisms. Nitroglycerin releases nitric oxide; sildenafil inhibits PDE5 preventing cGMP breakdown. Combined effect causes severe, potentially fatal blood pressure drop. This combination is absolutely contraindicated. Symptoms: severe dizziness, fainting, chest pain, cardiovascular collapse.",
        "source": "pubmed", "drug_pair": "nitroglycerin_sildenafil", "severity": "contraindicated",
    },
    {
        "id": "sertraline_tramadol_1",
        "text": "Sertraline and Tramadol serotonin syndrome: Sertraline is an SSRI that increases serotonin. Tramadol inhibits serotonin reuptake and is a weak opioid. Combined use can cause serotonin syndrome — a life-threatening condition. Symptoms include high fever, rapid heart rate, muscle rigidity, agitation, seizures, and loss of consciousness. Requires immediate medical attention.",
        "source": "pubmed", "drug_pair": "sertraline_tramadol", "severity": "contraindicated",
    },
    {
        "id": "methotrexate_trimethoprim_1",
        "text": "Methotrexate and Trimethoprim bone marrow suppression: Both drugs inhibit dihydrofolate reductase, depleting folate stores. Combined use causes additive antifolate toxicity leading to serious bone marrow suppression. Results in pancytopenia — dangerously low red cells, white cells, and platelets. Symptoms: unusual fatigue, infections, easy bruising, mouth ulcers. Monitor blood counts closely.",
        "source": "pubmed", "drug_pair": "methotrexate_trimethoprim", "severity": "contraindicated",
    },
    {
        "id": "amiodarone_warfarin_1",
        "text": "Amiodarone and Warfarin elevated INR: Amiodarone is a potent inhibitor of CYP2C9, the enzyme that metabolizes warfarin. Co-administration dramatically increases warfarin plasma levels, causing elevated INR and severe bleeding risk. Effect may persist weeks after stopping amiodarone. Warfarin dose must be reduced by 30-50%. Monitor INR weekly during initiation.",
        "source": "openfda", "drug_pair": "amiodarone_warfarin", "severity": "contraindicated",
    },

    # ── MAJOR PAIRS ────────────────────────────────────────────────
    {
        "id": "warfarin_ibuprofen_1",
        "text": "Warfarin and Ibuprofen GI bleeding: Ibuprofen is an NSAID that inhibits COX enzymes, reducing prostaglandin synthesis. This damages gastric mucosa and inhibits platelet function. Combined with warfarin's anticoagulant effect, risk of GI bleeding is significantly elevated. Also, ibuprofen can displace warfarin from plasma protein binding, increasing free warfarin levels. Use paracetamol instead if pain relief needed.",
        "source": "openfda", "drug_pair": "warfarin_ibuprofen", "severity": "severe",
    },
    {
        "id": "simvastatin_clarithromycin_1",
        "text": "Simvastatin and Clarithromycin rhabdomyolysis risk: Clarithromycin is a potent CYP3A4 inhibitor. Simvastatin is extensively metabolized by CYP3A4. Co-administration increases simvastatin AUC by 10-fold, causing myopathy and rhabdomyolysis — a serious breakdown of muscle tissue. Symptoms: severe muscle pain, weakness, dark brown urine. Kidney failure can result. Avoid this combination or suspend statin therapy during antibiotic course.",
        "source": "pubmed", "drug_pair": "simvastatin_clarithromycin", "severity": "severe",
    },
    {
        "id": "digoxin_verapamil_1",
        "text": "Digoxin and Verapamil toxicity risk: Verapamil inhibits P-glycoprotein, reducing digoxin renal clearance, and also inhibits CYP3A4 metabolism. This significantly increases digoxin serum levels. Digoxin has a narrow therapeutic window. Toxicity symptoms: nausea, vomiting, visual disturbances (yellow-green halos), bradycardia, and life-threatening arrhythmias. Reduce digoxin dose by 30-50% and monitor levels closely.",
        "source": "openfda", "drug_pair": "digoxin_verapamil", "severity": "severe",
    },
    {
        "id": "lisinopril_spironolactone_1",
        "text": "Lisinopril and Spironolactone hyperkalemia: ACE inhibitors like lisinopril reduce aldosterone, decreasing potassium excretion. Spironolactone is a potassium-sparing diuretic with the same effect. Combined use can cause dangerous hyperkalemia (high blood potassium). Symptoms: muscle weakness, irregular heartbeat, cardiac arrest at very high levels. Monitor serum potassium and renal function regularly.",
        "source": "pubmed", "drug_pair": "lisinopril_spironolactone", "severity": "severe",
    },
    {
        "id": "fluoxetine_tramadol_1",
        "text": "Fluoxetine and Tramadol serotonin syndrome: Fluoxetine inhibits serotonin reuptake (SSRI). Tramadol also inhibits serotonin reuptake and mu-opioid receptor agonism. Together they raise serotonin levels dangerously. Also, fluoxetine inhibits CYP2D6 which metabolizes tramadol, increasing tramadol levels further. Risk of serotonin syndrome and seizures. Symptoms: agitation, sweating, tremor, hyperthermia.",
        "source": "pubmed", "drug_pair": "fluoxetine_tramadol", "severity": "severe",
    },
    {
        "id": "digoxin_amiodarone_1",
        "text": "Digoxin and Amiodarone toxicity: Amiodarone inhibits P-glycoprotein and reduces renal clearance of digoxin. It also inhibits CYP3A4 metabolism. Both mechanisms increase digoxin plasma concentrations significantly. Given digoxin's narrow therapeutic index, toxicity is likely without dose adjustment. Reduce digoxin dose by 30-50% when starting amiodarone. Monitor ECG and digoxin serum levels.",
        "source": "pubmed", "drug_pair": "digoxin_amiodarone", "severity": "severe",
    },
    {
        "id": "clopidogrel_omeprazole_1",
        "text": "Clopidogrel and Omeprazole reduced efficacy: Clopidogrel is a prodrug activated by CYP2C19. Omeprazole is a strong CYP2C19 inhibitor. Co-administration reduces clopidogrel activation by up to 45%, significantly reducing its antiplatelet effect. This increases risk of cardiovascular events in patients relying on clopidogrel for heart protection. Consider using pantoprazole instead if a PPI is needed.",
        "source": "openfda", "drug_pair": "clopidogrel_omeprazole", "severity": "severe",
    },
    {
        "id": "amlodipine_simvastatin_1",
        "text": "Amlodipine and Simvastatin statin toxicity: Amlodipine mildly inhibits CYP3A4, the enzyme responsible for simvastatin metabolism. Co-administration can increase simvastatin exposure. FDA recommends not exceeding simvastatin 20mg/day when used with amlodipine. Higher doses increase risk of myopathy and rhabdomyolysis. Symptoms: muscle pain, weakness, dark urine. Monitor CK levels if symptoms develop.",
        "source": "openfda", "drug_pair": "amlodipine_simvastatin", "severity": "severe",
    },
    {
        "id": "ketoconazole_alprazolam_1",
        "text": "Ketoconazole and Alprazolam CNS depression: Ketoconazole is a potent CYP3A4 inhibitor. Alprazolam (a benzodiazepine) is primarily metabolized by CYP3A4. Co-administration increases alprazolam plasma levels significantly, causing excessive sedation, respiratory depression, and CNS depression. Patients may experience extreme drowsiness, confusion, impaired coordination. Avoid combination or reduce alprazolam dose with careful monitoring.",
        "source": "pubmed", "drug_pair": "ketoconazole_alprazolam", "severity": "severe",
    },
    {
        "id": "ciprofloxacin_tizanidine_1",
        "text": "Ciprofloxacin and Tizanidine excess sedation: Ciprofloxacin is a strong CYP1A2 inhibitor. Tizanidine is a muscle relaxant extensively metabolized by CYP1A2. Co-administration increases tizanidine AUC by 10-fold, causing profound hypotension, sedation, and CNS depression. This combination is contraindicated. Symptoms: extreme drowsiness, dizziness, dangerously low blood pressure.",
        "source": "pubmed", "drug_pair": "ciprofloxacin_tizanidine", "severity": "severe",
    },

    # ── MODERATE PAIRS ─────────────────────────────────────────────
    {
        "id": "metformin_prednisone_1",
        "text": "Metformin and Prednisone blood sugar elevation: Corticosteroids like prednisone raise blood glucose by stimulating gluconeogenesis and reducing insulin sensitivity. This directly counteracts metformin's glucose-lowering effect. Diabetic patients on metformin may experience hyperglycemia when prednisone is added. Monitor blood glucose more frequently. Temporary dose adjustment of metformin or addition of insulin may be needed.",
        "source": "openfda", "drug_pair": "metformin_prednisone", "severity": "moderate",
    },
    {
        "id": "levothyroxine_calcium_1",
        "text": "Levothyroxine and Calcium Carbonate absorption: Calcium carbonate binds to levothyroxine in the gastrointestinal tract, forming insoluble complexes that cannot be absorbed. This reduces levothyroxine bioavailability by up to 40%, leading to hypothyroidism if not managed. Take levothyroxine at least 4 hours before or after calcium supplements. Monitor thyroid function (TSH) when starting calcium supplements.",
        "source": "openfda", "drug_pair": "levothyroxine_calcium carbonate", "severity": "moderate",
    },
    {
        "id": "fluoxetine_ondansetron_1",
        "text": "Fluoxetine and Ondansetron QT prolongation: Both drugs prolong the cardiac QT interval through different mechanisms. Fluoxetine blocks cardiac potassium channels; ondansetron blocks hERG channels. Combined use increases risk of QT prolongation and potentially fatal Torsades de Pointes arrhythmia. Patients with pre-existing cardiac conditions are at highest risk. Monitor ECG and electrolytes. Avoid in patients with long QT syndrome.",
        "source": "pubmed", "drug_pair": "fluoxetine_ondansetron", "severity": "moderate",
    },
    {
        "id": "losartan_ibuprofen_1",
        "text": "Losartan and Ibuprofen kidney impairment: NSAIDs like ibuprofen reduce prostaglandin synthesis in kidneys. Prostaglandins help maintain renal blood flow, especially in patients on ARBs (losartan) or ACE inhibitors. Combined use can cause acute kidney injury, reduced antihypertensive effect, and sodium retention. Monitor renal function and blood pressure. Use paracetamol for pain relief instead.",
        "source": "openfda", "drug_pair": "losartan_ibuprofen", "severity": "moderate",
    },
    {
        "id": "insulin_propranolol_1",
        "text": "Insulin and Propranolol masked hypoglycemia: Beta-blockers like propranolol mask the adrenergic symptoms of hypoglycemia (tremor, palpitations, anxiety) that warn patients of low blood sugar. The only symptom remaining is sweating. Also, propranolol inhibits glycogenolysis, prolonging hypoglycemic episodes. Diabetic patients must monitor blood glucose more frequently. Prefer cardioselective beta-blockers when needed.",
        "source": "pubmed", "drug_pair": "insulin_propranolol", "severity": "moderate",
    },
    {
        "id": "lithium_hydrochlorothiazide_1",
        "text": "Lithium and Hydrochlorothiazide toxicity: Thiazide diuretics like hydrochlorothiazide cause sodium depletion. The kidneys compensate by reabsorbing more sodium — and lithium along with it, since lithium is transported similarly. This reduces lithium clearance and increases lithium blood levels toward the toxic range. Symptoms of lithium toxicity: tremor, confusion, ataxia, seizures. Monitor lithium levels and adjust dose.",
        "source": "pubmed", "drug_pair": "lithium_hydrochlorothiazide", "severity": "moderate",
    },
    {
        "id": "furosemide_digoxin_1",
        "text": "Furosemide and Digoxin electrolyte imbalance: Furosemide causes significant potassium and magnesium loss through urine. Hypokalemia increases digoxin binding to cardiac cells and its toxic effects. Even normal digoxin levels become toxic when potassium is low. Monitor potassium and magnesium levels regularly. Supplement potassium if needed. Watch for digoxin toxicity signs: nausea, visual changes, arrhythmias.",
        "source": "openfda", "drug_pair": "furosemide_digoxin", "severity": "moderate",
    },

    # ── MINOR / SAFE PAIRS ─────────────────────────────────────────
    {
        "id": "paracetamol_amoxicillin_1",
        "text": "Paracetamol and Amoxicillin minimal interaction: These two drugs have no clinically significant pharmacokinetic or pharmacodynamic interaction. Paracetamol is metabolized primarily in the liver; amoxicillin is excreted renally without hepatic metabolism. They can be safely used together for treating pain or fever alongside bacterial infections. No dose adjustment needed. Safe combination for most patients.",
        "source": "openfda", "drug_pair": "paracetamol_amoxicillin", "severity": "mild",
    },
    {
        "id": "cetirizine_paracetamol_1",
        "text": "Cetirizine and Paracetamol mild drowsiness: Cetirizine is a second-generation antihistamine with low sedation potential. Paracetamol is an analgesic with no significant CNS effects. Combined use may cause mild drowsiness in some individuals due to cetirizine's residual antihistaminic properties. No pharmacokinetic interaction exists. This is a commonly used and generally safe combination for allergic conditions with associated pain or fever.",
        "source": "openfda", "drug_pair": "cetirizine_paracetamol", "severity": "mild",
    },
    {
        "id": "vitamind_calcium_1",
        "text": "Vitamin D and Calcium Carbonate beneficial combination: This is actually a beneficial, commonly recommended combination. Vitamin D enhances intestinal absorption of calcium by upregulating calcium transport proteins. Together they effectively maintain bone health and prevent osteoporosis. No adverse interaction exists. Standard supplementation for bone health, especially in elderly patients and postmenopausal women. Monitor calcium levels in patients with kidney disease.",
        "source": "pubmed", "drug_pair": "vitamin d_calcium carbonate", "severity": "mild",
    },
    {
        "id": "metformin_atorvastatin_1",
        "text": "Metformin and Atorvastatin generally safe: This is a very commonly prescribed combination for type 2 diabetic patients with dyslipidemia. No significant pharmacokinetic interaction exists between metformin and atorvastatin. Both drugs have different metabolic pathways. Some studies suggest statins may slightly increase insulin resistance, but the cardiovascular benefit outweighs this concern. Routine monitoring of blood glucose and lipid profile recommended.",
        "source": "openfda", "drug_pair": "metformin_atorvastatin", "severity": "mild",
    },
    {
        "id": "aspirin_atorvastatin_1",
        "text": "Aspirin and Atorvastatin common cardiac regimen: This combination is standard therapy for patients with cardiovascular disease or high cardiac risk. Low-dose aspirin prevents platelet aggregation; atorvastatin reduces LDL cholesterol and has anti-inflammatory effects. No clinically significant drug-drug interaction. Both drugs together reduce major adverse cardiovascular events. Routine monitoring of liver function and lipid panel recommended annually.",
        "source": "pubmed", "drug_pair": "aspirin_atorvastatin", "severity": "mild",
    },
    {
        "id": "levocetirizine_montelukast_1",
        "text": "Levocetirizine and Montelukast common allergy therapy: This is a standard combination prescribed for allergic rhinitis. Levocetirizine blocks H1 histamine receptors; montelukast blocks leukotriene receptors. They act via complementary mechanisms providing better symptom control than either alone. No significant pharmacokinetic interaction. Well tolerated. Mild drowsiness possible with levocetirizine. Safe for long-term use in patients with allergic rhinitis or asthma.",
        "source": "openfda", "drug_pair": "levocetirizine_montelukast", "severity": "mild",
    },
    {
        "id": "metoprolol_aspirin_1",
        "text": "Metoprolol and Aspirin common cardiovascular therapy: This combination is standard post-myocardial infarction therapy. Metoprolol (beta-blocker) reduces heart rate and myocardial oxygen demand; aspirin prevents platelet aggregation and clot formation. No pharmacokinetic interaction. NSAIDs in general can blunt the antihypertensive effect of beta-blockers, but low-dose aspirin has minimal effect. Safe and beneficial combination for cardiovascular patients.",
        "source": "pubmed", "drug_pair": "metoprolol_aspirin", "severity": "mild",
    },
    {
        "id": "azithromycin_paracetamol_1",
        "text": "Azithromycin and Paracetamol usually safe: No clinically relevant pharmacokinetic interaction exists between azithromycin and paracetamol. Azithromycin is metabolized by the liver (CYP3A4); paracetamol via glucuronidation and sulfation. They do not share metabolic pathways. This combination is commonly used to treat respiratory infections with associated fever or pain. Note: azithromycin alone can prolong QT interval — avoid in patients with cardiac risk factors.",
        "source": "openfda", "drug_pair": "azithromycin_paracetamol", "severity": "mild",
    },
    {
        "id": "esomeprazole_domperidone_1",
        "text": "Esomeprazole and Domperidone low interaction: Esomeprazole (PPI) reduces gastric acid; domperidone promotes gastric motility. Together they are commonly used for GERD and gastroparesis. Domperidone is metabolized by CYP3A4; esomeprazole mildly inhibits CYP2C19 but does not significantly affect domperidone levels. Note: domperidone has mild QT-prolonging potential. Avoid high doses in elderly or cardiac patients. Generally safe at standard doses.",
        "source": "openfda", "drug_pair": "esomeprazole_domperidone", "severity": "mild",
    },
    {
        "id": "pantoprazole_paracetamol_1",
        "text": "Pantoprazole and Paracetamol low interaction: No clinically significant drug interaction exists between pantoprazole and paracetamol. Pantoprazole reduces gastric acid by irreversibly blocking the proton pump. Paracetamol provides analgesia and antipyresis. Different metabolic pathways — no competition. Pantoprazole is often used to protect the gastric mucosa in patients on long-term paracetamol. Safe combination routinely used in clinical practice.",
        "source": "openfda", "drug_pair": "pantoprazole_paracetamol", "severity": "mild",
    },

    # ── NEW CONTRAINDICATED ────────────────────────────────────────
    {
        "id": "isocarboxazid_fluoxetine_1",
        "text": "Isocarboxazid and Fluoxetine serotonin syndrome risk: Isocarboxazid is a non-selective MAO inhibitor; fluoxetine is an SSRI. Combining MAOIs with SSRIs causes catastrophic serotonin accumulation. Serotonin syndrome is life-threatening: hyperthermia, hypertension, tachycardia, severe agitation, muscle rigidity, seizures, cardiovascular collapse. Allow 14 days washout after stopping isocarboxazid before starting fluoxetine. Allow 5 weeks washout after fluoxetine before starting any MAOI. Absolutely contraindicated.",
        "source": "pubmed", "drug_pair": "isocarboxazid_fluoxetine", "severity": "contraindicated",
    },
    {
        "id": "linezolid_sertraline_1",
        "text": "Linezolid and Sertraline serotonin syndrome: Linezolid is a weak, non-selective MAO inhibitor in addition to being an antibiotic. Sertraline is an SSRI that increases serotonergic activity. Co-administration can cause serotonin syndrome. Symptoms: agitation, fever, rapid heart rate, muscle twitching, loss of coordination, seizures. This combination is contraindicated. If linezolid is urgently needed, sertraline must be stopped. Allow 14 days washout before restarting sertraline after linezolid.",
        "source": "pubmed", "drug_pair": "linezolid_sertraline", "severity": "contraindicated",
    },
    {
        "id": "simvastatin_ketoconazole_1",
        "text": "Simvastatin and Ketoconazole rhabdomyolysis risk: Ketoconazole is a potent CYP3A4 inhibitor. Simvastatin is extensively metabolized by CYP3A4. Co-administration increases simvastatin AUC by up to 20-fold, causing severe myopathy and rhabdomyolysis — dangerous muscle tissue breakdown leading to kidney failure. Symptoms: severe muscle pain, weakness, dark urine. This combination is contraindicated. Switch to pravastatin or rosuvastatin, which are not significantly metabolized by CYP3A4.",
        "source": "pubmed", "drug_pair": "simvastatin_ketoconazole", "severity": "contraindicated",
    },
    {
        "id": "simvastatin_itraconazole_1",
        "text": "Simvastatin and Itraconazole severe statin toxicity: Itraconazole is a potent CYP3A4 inhibitor. Simvastatin relies on CYP3A4 for metabolism. Itraconazole increases simvastatin plasma levels by up to 20-fold, causing myopathy and life-threatening rhabdomyolysis. FDA has contraindicated this combination. Simvastatin must be suspended during itraconazole therapy. Alternative: switch to pravastatin, rosuvastatin, or fluvastatin which are not significantly metabolized by CYP3A4.",
        "source": "openfda", "drug_pair": "simvastatin_itraconazole", "severity": "contraindicated",
    },
    {
        "id": "simvastatin_gemfibrozil_1",
        "text": "Simvastatin and Gemfibrozil rhabdomyolysis: Gemfibrozil inhibits simvastatin metabolism via CYP2C8 and glucuronidation pathways and competes for protein binding. This dramatically increases simvastatin exposure. FDA has contraindicated this combination — risk of rhabdomyolysis is 15-fold higher compared to simvastatin alone. Symptoms: muscle pain, weakness, dark urine, kidney failure. If fibrate therapy is needed with a statin, fenofibrate is the preferred safer alternative.",
        "source": "openfda", "drug_pair": "simvastatin_gemfibrozil", "severity": "contraindicated",
    },
    {
        "id": "warfarin_mifepristone_1",
        "text": "Warfarin and Mifepristone dangerous anticoagulation: Mifepristone inhibits CYP2C9 and CYP3A4, the enzymes responsible for warfarin metabolism. This significantly increases warfarin plasma levels and anticoagulant effect. Given that mifepristone is used to terminate pregnancy, concurrent warfarin use creates unacceptable hemorrhagic risk. This combination is absolutely contraindicated. Warfarin therapy must be reviewed and alternative anticoagulation management considered before mifepristone use.",
        "source": "pubmed", "drug_pair": "warfarin_mifepristone", "severity": "contraindicated",
    },
    {
        "id": "cisapride_ketoconazole_1",
        "text": "Cisapride and Ketoconazole fatal cardiac arrhythmia: Ketoconazole inhibits CYP3A4, the primary enzyme metabolizing cisapride. This causes extreme elevation of cisapride plasma levels. Cisapride blocks cardiac hERG potassium channels, causing prolonged QT interval and Torsades de Pointes — a potentially fatal ventricular arrhythmia. Multiple patient deaths led to cisapride withdrawal from many markets. This combination is absolutely contraindicated. Never co-administer.",
        "source": "pubmed", "drug_pair": "cisapride_ketoconazole", "severity": "contraindicated",
    },
    {
        "id": "pimozide_clarithromycin_1",
        "text": "Pimozide and Clarithromycin fatal QT prolongation: Clarithromycin is a potent CYP3A4 inhibitor and also independently prolongs QT interval. Pimozide is metabolized by CYP3A4 and is a potent QT-prolonging agent. Co-administration causes extreme QT prolongation leading to Torsades de Pointes, ventricular fibrillation, and sudden cardiac death. Multiple fatalities reported. This combination is absolutely contraindicated and carries a black box warning. Never combine.",
        "source": "pubmed", "drug_pair": "pimozide_clarithromycin", "severity": "contraindicated",
    },
    {
        "id": "ergotamine_ritonavir_1",
        "text": "Ergotamine and Ritonavir ergotism: Ritonavir is an extremely potent CYP3A4 inhibitor. Ergotamine is metabolized almost entirely by CYP3A4. Co-administration increases ergotamine plasma levels by up to 500-fold, causing severe ergotism: intense vasoconstriction of peripheral and cerebral vessels. Symptoms: limb ischemia, gangrene, stroke, seizures. Even small ergotamine doses become toxic. Absolutely contraindicated. Use alternative migraine treatments in HIV patients on ritonavir.",
        "source": "pubmed", "drug_pair": "ergotamine_ritonavir", "severity": "contraindicated",
    },

    # ── NEW SEVERE ─────────────────────────────────────────────────
    {
        "id": "methotrexate_ibuprofen_1",
        "text": "Methotrexate and Ibuprofen severe toxicity: NSAIDs like ibuprofen reduce renal blood flow and decrease methotrexate clearance via competing tubular secretion. This dramatically increases methotrexate plasma levels. Even low-dose methotrexate used for rheumatoid arthritis can become toxic. Effects: bone marrow suppression, hepatotoxicity, mucositis, pulmonary toxicity. Avoid all NSAIDs with methotrexate. Use paracetamol cautiously. Monitor CBC, renal function, and liver enzymes closely.",
        "source": "pubmed", "drug_pair": "methotrexate_ibuprofen", "severity": "severe",
    },
    {
        "id": "lithium_ibuprofen_1",
        "text": "Lithium and Ibuprofen toxicity: NSAIDs inhibit renal prostaglandins that regulate lithium excretion. Reduced renal clearance causes lithium accumulation to toxic levels. Lithium has a narrow therapeutic index. Ibuprofen can raise lithium levels by 25-60%. Toxicity symptoms: tremor, confusion, ataxia, nausea, polyuria, seizures, cardiac arrhythmias. Avoid all NSAIDs in lithium patients. Use paracetamol for pain relief. Monitor lithium serum levels closely.",
        "source": "pubmed", "drug_pair": "lithium_ibuprofen", "severity": "severe",
    },
    {
        "id": "warfarin_metronidazole_1",
        "text": "Warfarin and Metronidazole serious INR elevation: Metronidazole is a potent inhibitor of CYP2C9, the enzyme metabolizing active S-warfarin. It also inhibits CYP3A4 and reduces vitamin K availability by altering gut flora. Combined effect dramatically increases warfarin plasma levels and INR. Bleeding risk is significantly elevated. Reduce warfarin dose by 25-50%. Monitor INR every 2-3 days during metronidazole course and for one week after.",
        "source": "openfda", "drug_pair": "warfarin_metronidazole", "severity": "severe",
    },
    {
        "id": "warfarin_fluconazole_1",
        "text": "Warfarin and Fluconazole major INR elevation: Fluconazole is a potent CYP2C9 inhibitor. CYP2C9 is the primary enzyme metabolizing S-warfarin, the more pharmacologically active enantiomer. Even a single dose of fluconazole can significantly increase warfarin plasma levels and INR. Warfarin dose must be reduced (often by 50%). Monitor INR every 1-2 days during fluconazole therapy and for several days after. Watch for unusual bruising and bleeding.",
        "source": "pubmed", "drug_pair": "warfarin_fluconazole", "severity": "severe",
    },

    # ── NEW MODERATE ───────────────────────────────────────────────
    {
        "id": "lisinopril_ibuprofen_1",
        "text": "Lisinopril and Ibuprofen kidney impairment and reduced efficacy: NSAIDs like ibuprofen reduce renal prostaglandins that maintain glomerular filtration. Combined with ACE inhibitors like lisinopril, this can cause acute kidney injury, fluid retention, and reduced antihypertensive efficacy. Known as part of the dangerous triple whammy when a diuretic is also present. Monitor renal function and blood pressure. Use paracetamol for pain relief instead of ibuprofen.",
        "source": "openfda", "drug_pair": "lisinopril_ibuprofen", "severity": "moderate",
    },
    {
        "id": "aspirin_clopidogrel_1",
        "text": "Aspirin and Clopidogrel dual antiplatelet therapy: Both drugs inhibit platelet aggregation via different mechanisms — aspirin inhibits COX-1; clopidogrel blocks P2Y12 receptors. This combination is standard therapy after coronary stent placement and acute coronary syndrome. The combination significantly increases bleeding risk, especially GI bleeding. A proton pump inhibitor (preferably pantoprazole) should be co-prescribed. Any bleeding symptoms require immediate medical attention.",
        "source": "pubmed", "drug_pair": "aspirin_clopidogrel", "severity": "moderate",
    },
    {
        "id": "simvastatin_warfarin_1",
        "text": "Simvastatin and Warfarin elevated INR: Simvastatin inhibits CYP2C9, the primary enzyme metabolizing the more potent S-warfarin enantiomer. This increases warfarin plasma concentrations and INR. Bleeding risk is elevated. When starting simvastatin in a warfarin patient, monitor INR closely and consider warfarin dose reduction. Pravastatin or rosuvastatin have less CYP2C9 interaction and are safer alternatives.",
        "source": "pubmed", "drug_pair": "simvastatin_warfarin", "severity": "moderate",
    },
    {
        "id": "omeprazole_warfarin_1",
        "text": "Omeprazole and Warfarin mild INR increase: Omeprazole inhibits CYP2C19 and to some extent CYP2C9, which metabolize warfarin. Co-administration can increase warfarin plasma levels and raise INR. Effect is generally mild but clinically relevant in patients with narrow therapeutic INR ranges. Monitor INR when starting or stopping omeprazole. Pantoprazole has less CYP interaction and is preferred in warfarin patients requiring a PPI.",
        "source": "openfda", "drug_pair": "omeprazole_warfarin", "severity": "moderate",
    },
    {
        "id": "amoxicillin_warfarin_1",
        "text": "Amoxicillin and Warfarin increased bleeding risk: Amoxicillin can alter gut flora that produce vitamin K2, reducing its synthesis. Since warfarin works by blocking vitamin K-dependent clotting factors, reduced vitamin K availability potentiates anticoagulant effect, raising INR. Effect varies between individuals. Monitor INR during and after the antibiotic course. Watch for bleeding signs: unusual bruising, prolonged bleeding from cuts.",
        "source": "pubmed", "drug_pair": "amoxicillin_warfarin", "severity": "moderate",
    },
    {
        "id": "ibuprofen_digoxin_1",
        "text": "Ibuprofen and Digoxin toxicity risk: NSAIDs like ibuprofen reduce renal blood flow and glomerular filtration rate by inhibiting prostaglandins. Since digoxin is primarily eliminated renally, reduced renal function increases digoxin plasma levels. Digoxin has a very narrow therapeutic window. Elevated levels cause toxicity: nausea, visual disturbances (yellow-green halos), bradycardia, dangerous arrhythmias. Avoid NSAIDs in digoxin patients; use paracetamol. Monitor digoxin levels and renal function.",
        "source": "openfda", "drug_pair": "ibuprofen_digoxin", "severity": "moderate",
    },

    # ── NEW MILD ───────────────────────────────────────────────────
    {
        "id": "ibuprofen_paracetamol_1",
        "text": "Ibuprofen and Paracetamol mild synergistic use: These two analgesics act via different mechanisms — ibuprofen inhibits COX enzymes reducing prostaglandins; paracetamol acts centrally. Used together, they provide better pain control than either alone. No significant pharmacokinetic interaction. Risk of additive GI irritation with long-term use. Alternating doses is a common clinical strategy. Safe for short-term combined use at standard doses.",
        "source": "openfda", "drug_pair": "ibuprofen_paracetamol", "severity": "mild",
    },
    {
        "id": "cetirizine_diphenhydramine_1",
        "text": "Cetirizine and Diphenhydramine additive sedation: Both are antihistamines. Cetirizine is second-generation with low sedation. Diphenhydramine is first-generation with significant sedation and anticholinergic effects. Combining them increases CNS sedation risk. No serious pharmacokinetic interaction. Risk: excessive drowsiness, impaired driving, dry mouth, urinary retention. Particularly problematic in elderly patients. Avoid combining — choose one antihistamine instead.",
        "source": "openfda", "drug_pair": "cetirizine_diphenhydramine", "severity": "mild",
    },
    {
        "id": "amlodipine_sildenafil_1",
        "text": "Amlodipine and Sildenafil mild blood pressure lowering: Both drugs lower blood pressure by different mechanisms — amlodipine blocks calcium channels; sildenafil inhibits PDE5. Combined use can cause additive hypotension. Symptoms: dizziness, lightheadedness, flushing. Unlike nitrates, this combination is not absolutely contraindicated but requires caution. Use the lowest effective sildenafil dose; monitor blood pressure. Avoid in patients with significant cardiovascular instability.",
        "source": "pubmed", "drug_pair": "amlodipine_sildenafil", "severity": "mild",
    },
    {
        "id": "warfarin_paracetamol_1",
        "text": "Warfarin and Paracetamol mild INR elevation: Paracetamol at high doses (>2g/day regularly) can mildly elevate INR in patients on warfarin. The mechanism may involve CYP2C9 inhibition or reduced synthesis of clotting factors. At standard doses (<2g/day), the interaction is minimal. Paracetamol remains the preferred analgesic over NSAIDs for warfarin patients. Monitor INR if paracetamol use is regular or high-dose.",
        "source": "openfda", "drug_pair": "warfarin_paracetamol", "severity": "mild",
    },
    {
        "id": "prednisone_ibuprofen_1",
        "text": "Prednisone and Ibuprofen GI irritation risk: Both drugs can irritate the gastric mucosa. Prednisone reduces the protective mucus lining; ibuprofen inhibits prostaglandin synthesis, impairing mucosal defense. Combined use significantly increases risk of peptic ulcers and GI bleeding compared to either drug alone. Risk is manageable with a proton pump inhibitor (e.g., omeprazole). Use at lowest effective doses and for the shortest duration.",
        "source": "openfda", "drug_pair": "prednisone_ibuprofen", "severity": "mild",
    },
    {
        "id": "omeprazole_iron_1",
        "text": "Omeprazole and Iron reduced absorption: Gastric acid is required to convert dietary iron (Fe³⁺) to the absorbable ferrous form (Fe²⁺). Omeprazole reduces gastric acid, impairing iron absorption by 40-50%. In patients taking iron supplements for deficiency, this reduces treatment efficacy. Take iron supplements at least 2 hours before omeprazole if possible. Ferric carboxymaltose injections are not affected by gastric pH and may be considered for severe deficiency.",
        "source": "pubmed", "drug_pair": "omeprazole_iron", "severity": "mild",
    },
    {
        "id": "amoxicillin_oral_contraceptives_1",
        "text": "Amoxicillin and Oral Contraceptives theoretical reduced efficacy: Historically believed that antibiotics reduce oral contraceptive efficacy by altering gut bacteria that recycle ethinylestradiol. Current evidence shows this effect is minimal with amoxicillin. Most guidelines no longer recommend additional contraception for short antibiotic courses. However, patients with GI side effects such as vomiting or diarrhea should use backup contraception as absorption may be impaired.",
        "source": "pubmed", "drug_pair": "amoxicillin_oral contraceptives", "severity": "mild",
    },
    {
        "id": "lisinopril_aspirin_1",
        "text": "Lisinopril and Aspirin reduced ACE inhibitor efficacy: Low-dose aspirin inhibits COX-2, reducing prostaglandin synthesis. Prostaglandins contribute to the vasodilatory effects of ACE inhibitors like lisinopril. High-dose aspirin may reduce lisinopril's antihypertensive and cardioprotective effects. Low-dose aspirin (75-100mg) has minimal impact and is commonly co-prescribed in cardiovascular patients. Monitor blood pressure when both drugs are used together.",
        "source": "openfda", "drug_pair": "lisinopril_aspirin", "severity": "mild",
    },
    {
        "id": "omeprazole_vitamin_b12_1",
        "text": "Omeprazole and Vitamin B12 reduced absorption: Vitamin B12 requires gastric acid for separation from dietary protein and intrinsic factor binding. Long-term omeprazole use (>1 year) reduces gastric acid, impairing B12 absorption. This can lead to B12 deficiency with symptoms: fatigue, peripheral neuropathy, megaloblastic anemia, cognitive changes. Check B12 levels annually in patients on long-term PPI therapy. Supplement with oral or injectable B12 if levels are low.",
        "source": "pubmed", "drug_pair": "omeprazole_vitamin b12", "severity": "mild",
    },

    # ── NEW NONE ───────────────────────────────────────────────────
    {
        "id": "metformin_insulin_1",
        "text": "Metformin and Insulin complementary therapy: Metformin reduces hepatic glucose production and improves insulin sensitivity. Insulin provides direct glucose uptake stimulation. When combined, they work complementarily to control blood sugar in type 2 diabetes. No pharmacokinetic interaction. Monitor blood glucose to avoid hypoglycemia, especially with higher insulin doses. Dose adjustment of either agent may be needed as glucose control improves.",
        "source": "openfda", "drug_pair": "metformin_insulin", "severity": "none",
    },
    {
        "id": "omeprazole_paracetamol_1",
        "text": "Omeprazole and Paracetamol no significant interaction: Omeprazole reduces gastric acid through proton pump inhibition. Paracetamol is metabolized via hepatic glucuronidation and sulfation. These drugs use completely different metabolic pathways with no pharmacokinetic interaction. This is a common and safe combination. Omeprazole may be co-prescribed to protect the gastric lining in patients requiring regular paracetamol use.",
        "source": "openfda", "drug_pair": "omeprazole_paracetamol", "severity": "none",
    },
    {
        "id": "amlodipine_paracetamol_1",
        "text": "Amlodipine and Paracetamol no interaction: Amlodipine is a calcium channel blocker metabolized by CYP3A4. Paracetamol is metabolized primarily by glucuronidation. No clinically significant pharmacokinetic or pharmacodynamic interaction exists between these drugs. Paracetamol is the preferred analgesic for patients on antihypertensive therapy. Safe and commonly used together in hypertensive patients requiring pain relief.",
        "source": "openfda", "drug_pair": "amlodipine_paracetamol", "severity": "none",
    },
    {
        "id": "levothyroxine_paracetamol_1",
        "text": "Levothyroxine and Paracetamol no significant interaction: Levothyroxine replaces thyroid hormone and is absorbed in the small intestine. Paracetamol does not affect thyroid hormone absorption or metabolism. No clinically significant interaction exists. Paracetamol is the analgesic of choice for hypothyroid patients on levothyroxine replacement therapy. Safe combination at standard doses with no dose adjustment required.",
        "source": "openfda", "drug_pair": "levothyroxine_paracetamol", "severity": "none",
    },
    {
        "id": "losartan_paracetamol_1",
        "text": "Losartan and Paracetamol preferred safe combination: Losartan is an ARB antihypertensive metabolized by CYP2C9 and CYP3A4. Paracetamol does not significantly affect these enzymes or blood pressure. Unlike NSAIDs, paracetamol does not reduce the antihypertensive effect of losartan or worsen renal function. Paracetamol is specifically recommended as the analgesic of choice for patients on ARBs. No clinically significant interaction at standard doses.",
        "source": "openfda", "drug_pair": "losartan_paracetamol", "severity": "none",
    },
]


class RAGService:
    """
    RAG service for drug interaction explanations.

    Data sources (priority order):
      1. RxNorm Drug Interaction API  — NIH, free, no key, real-time
      2. OpenFDA Drug Label API       — FDA, free, no key, real-time
      3. ChromaDB                     — local vector store (auto-populated from above)
      4. SEED_DATA                    — fallback for cold start / offline mode
    """

    def __init__(self):
        self.chroma_client: Optional[chromadb.PersistentClient] = None
        self.collection = None
        self.groq_client: Optional[AsyncGroq] = None
        self._initialized = False
        self._http_client: Optional[httpx.AsyncClient] = None
        # In-memory set to avoid re-fetching the same pair in a session.
        # ChromaDB volume persists results across restarts, so this is only
        # needed to deduplicate within a single container lifetime.
        self._realtime_fetched: set = set()

    async def initialize(self):
        # Only create the Groq client at startup — it's lightweight (~0 MB).
        # ChromaDB + sentence-transformer (~350 MB) are loaded lazily on the
        # first real request so Docker startup RAM stays below 200 MB.
        self.groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._initialized = True
        logger.info("RAG service initialized (ChromaDB loads on first request)")

    # ──────────────────────────────────────────────────────────────────
    # Real-time data fetching — RxNorm + OpenFDA
    # ──────────────────────────────────────────────────────────────────

    async def _get_rxcui(self, drug_name: str) -> Optional[str]:
        """Resolve a drug name to its RxNorm CUI (concept identifier)."""
        try:
            resp = await self._http_client.get(
                f"{RXNORM_BASE}/rxcui.json",
                params={"name": drug_name, "search": 1},
            )
            if resp.status_code == 200:
                ids = resp.json().get("idGroup", {}).get("rxnormId", [])
                return ids[0] if ids else None
        except Exception as e:
            logger.debug(f"RxCUI lookup failed for '{drug_name}': {e}")
        return None

    async def _fetch_rxnorm_interaction(self, drug_a: str, drug_b: str) -> Optional[str]:
        """
        Query RxNorm Drug Interaction API.
        Returns a clinical description string if an interaction is found.
        """
        rxcui = await self._get_rxcui(drug_a)
        if not rxcui:
            return None
        try:
            resp = await self._http_client.get(
                f"{RXNORM_BASE}/interaction/interaction.json",
                params={"rxcui": rxcui, "sources": "DrugBank,ONCHigh"},
            )
            if resp.status_code != 200:
                return None

            drug_b_lower = drug_b.lower()
            for group in resp.json().get("interactionTypeGroup", []):
                for itype in group.get("interactionType", []):
                    for pair in itype.get("interactionPair", []):
                        concept_names = [
                            c.get("minConceptItem", {}).get("name", "").lower()
                            for c in pair.get("interactionConcept", [])
                        ]
                        if any(drug_b_lower in name or name in drug_b_lower for name in concept_names):
                            desc = pair.get("description", "")
                            severity_val = pair.get("severity", "")
                            if desc:
                                return f"[RxNorm | Severity: {severity_val}] {desc}"
        except Exception as e:
            logger.debug(f"RxNorm interaction fetch failed for {drug_a}+{drug_b}: {e}")
        return None

    async def _fetch_openfda_label(self, drug_a: str, drug_b: str) -> Optional[str]:
        """
        Query OpenFDA Drug Label API for interaction warnings mentioning drug_b.
        """
        try:
            resp = await self._http_client.get(
                f"{OPENFDA_BASE}/label.json",
                params={
                    "search": f'drug_interactions:"{drug_a}"',
                    "limit": 3,
                },
            )
            if resp.status_code != 200:
                return None

            drug_b_lower = drug_b.lower()
            for result in resp.json().get("results", []):
                for text in result.get("drug_interactions", []):
                    if drug_b_lower in text.lower():
                        return f"[FDA Label] {text[:700]}"
        except Exception as e:
            logger.debug(f"OpenFDA label fetch failed for {drug_a}+{drug_b}: {e}")
        return None

    async def _fetch_and_store_realtime(self, drug_a: str, drug_b: str) -> None:
        """
        Fetch real-time interaction data from RxNorm + OpenFDA and upsert into ChromaDB.
        Results persist across restarts via the chroma_data Docker volume.
        """
        if not self._http_client or not self.collection:
            return

        pair_key = "_".join(sorted([drug_a.lower(), drug_b.lower()]))
        if pair_key in self._realtime_fetched:
            return  # already fetched this session

        # Run both API calls concurrently
        rxnorm_text, openfda_text = await asyncio.gather(
            self._fetch_rxnorm_interaction(drug_a, drug_b),
            self._fetch_openfda_label(drug_a, drug_b),
            return_exceptions=True,
        )

        added = 0
        for source_label, text in [("rxnorm", rxnorm_text), ("openfda_rt", openfda_text)]:
            if not isinstance(text, str) or not text.strip():
                continue
            doc_id = f"{source_label}_{pair_key}_realtime"
            try:
                # get() returns only ids that already exist — skip if found
                existing = self.collection.get(ids=[doc_id])["ids"]
                if existing:
                    continue
                self.collection.add(
                    ids=[doc_id],
                    documents=[f"Drug interaction {drug_a} + {drug_b}: {text}"],
                    metadatas=[{
                        "source": source_label,
                        "drug_pair": pair_key,
                        "severity": "unknown",
                        "realtime": "true",
                    }],
                )
                added += 1
            except Exception as e:
                logger.debug(f"ChromaDB upsert skipped ({doc_id}): {e}")

        self._realtime_fetched.add(pair_key)
        if added:
            logger.info(f"Real-time: stored {added} new docs for {drug_a}+{drug_b} (total: {self.collection.count()})")

    async def _ensure_chroma_ready(self):
        """Load ChromaDB + sentence-transformer model on first use."""
        if self.chroma_client is None:
            logger.info("Lazy-loading ChromaDB + sentence-transformer model...")
            await asyncio.get_event_loop().run_in_executor(None, self._setup_chroma)
            logger.info("ChromaDB ready")

    def _setup_chroma(self):
        try:
            self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)
            embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name="drug_interactions",
                embedding_function=embedding_fn,
                metadata={"hnsw:space": "cosine"},
            )
            self._sync_seed_data()
            logger.info(f"ChromaDB ready: {self.collection.count()} documents")
        except Exception as e:
            logger.error(f"ChromaDB setup failed: {e}")
            self.collection = None

    def _sync_seed_data(self):
        """Upsert all SEED_DATA so new entries are added without wiping existing ones."""
        existing_ids = set(self.collection.get(ids=[d["id"] for d in SEED_DATA])["ids"])
        new_entries = [d for d in SEED_DATA if d["id"] not in existing_ids]
        if new_entries:
            self.collection.add(
                ids=[d["id"] for d in new_entries],
                documents=[d["text"] for d in new_entries],
                metadatas=[
                    {"source": d["source"], "drug_pair": d["drug_pair"], "severity": d["severity"]}
                    for d in new_entries
                ],
            )
            logger.info(f"ChromaDB: added {len(new_entries)} new documents (total: {self.collection.count()})")
        else:
            logger.info(f"ChromaDB: all {self.collection.count()} documents up to date")

    async def retrieve_sources(self, drug_a: str, drug_b: str, n_results: int = 4) -> list:
        await self._ensure_chroma_ready()
        if not self.collection:
            return []

        # ── Step 1: Fetch real-time data and store in ChromaDB ────────
        # Timeout guards against slow API responses blocking the user.
        try:
            await asyncio.wait_for(
                self._fetch_and_store_realtime(drug_a, drug_b),
                timeout=7.0,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Real-time fetch timed out for {drug_a}+{drug_b}, using cached data")
        except Exception as e:
            logger.warning(f"Real-time fetch error: {e}")

        # ── Step 2: Semantic search across ChromaDB ───────────────────
        # ChromaDB now contains both seed data AND fresh real-time results.
        query = (
            f"drug interaction between {drug_a} and {drug_b} "
            f"clinical effects risks mechanism severity"
        )
        try:
            count = self.collection.count()
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.collection.query(
                    query_texts=[query],
                    n_results=min(n_results, max(count, 1)),
                    include=["documents", "metadatas", "distances"],
                ),
            )
            sources = []
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                src = meta.get("source", "openfda")
                sources.append(
                    DrugSource(
                        title=f"Drug Interaction Reference: {drug_a} + {drug_b}",
                        source=src,
                        url=self._build_url(src, drug_a, drug_b),
                        snippet=doc[:400] + "..." if len(doc) > 400 else doc,
                    )
                )
            return sources
        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}")
            return []

    def _build_url(self, source: str, drug_a: str, drug_b: str) -> str:
        if source == "pubmed":
            q = f"{drug_a}+{drug_b}+interaction".replace(" ", "+")
            return f"https://pubmed.ncbi.nlm.nih.gov/?term={q}"
        if source == "rxnorm":
            return f"https://rxnav.nlm.nih.gov/REST/interaction/list.json?names={drug_a};{drug_b}"
        return (
            f"https://api.fda.gov/drug/label.json"
            f"?search=drug_interactions:{drug_a}&limit=3"
        )

    async def stream_explanation(self, drug_a: str, drug_b: str, severity: str, sources: list) -> AsyncGenerator[str, None]:
        if not self.groq_client:
            yield "RAG service not initialized. Please check GROQ_API_KEY."
            return

        context = "\n\n".join([s.snippet for s in sources]) if sources else ""
        user_prompt = f"""Analyze the drug-drug interaction between {drug_a} and {drug_b}.

Predicted Severity: {severity.upper()}

Relevant Clinical Context:
{context if context else "Use general pharmacological knowledge for this drug pair."}

Please provide:
1. Why this interaction occurs (mechanism)
2. What clinical effects to watch for (symptoms)
3. How serious this is for the patient
4. Monitoring recommendations
5. When to seek immediate medical attention

Keep your response clear, accurate, and helpful for patients and caregivers."""

        try:
            stream = await self.groq_client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=500,
                temperature=0.3,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Groq streaming failed: {e}")
            yield self._fallback_explanation(drug_a, drug_b, severity)

    def _fallback_explanation(self, drug_a: str, drug_b: str, severity: str) -> str:
        severity_messages = {
            "critical": f"The combination of {drug_a} and {drug_b} is potentially dangerous and may require immediate medical attention. This is classified as a CRITICAL interaction.",
            "major": f"The combination of {drug_a} and {drug_b} carries significant risk and requires medical supervision. Do not start or stop either medication without consulting your doctor.",
            "moderate": f"The combination of {drug_a} and {drug_b} requires monitoring. Inform your healthcare provider about both medications.",
            "minor": f"The combination of {drug_a} and {drug_b} has minimal interaction risk. Continue as directed by your doctor.",
        }
        return severity_messages.get(
            severity.lower(),
            f"Please consult your healthcare provider before taking {drug_a} and {drug_b} together."
        )


# Singleton
rag_service = RAGService()
