import streamlit as st
import pandas as pd
from typing import Optional, List

from clients.smartlead.index import (
    SmartleadCampaignSequenceInput,
    add_sequences_to_campaign,
    get_campaign_sequences,
    get_campaign_statistics,
    get_campaigns,
)
from clients.smartlead.internal.index import (
    update_smartlead_campaign_follow_up_percentage,
)
from clients.smartlead.schema import SeqDelayDetailsInput, SequenceVariantInput

st.title("Add Follow-ups to Smartlead Campaigns")

ss = st.session_state
ss.setdefault("all_campaigns", [])
ss.setdefault("selected_campaigns", [])
ss.setdefault("delay_period", 0)
ss.setdefault("change_follow_up_percentage", False)
ss.setdefault("running_add_followups", False)
ss.setdefault("successful_campaigns", [])
ss.setdefault("failed_campaigns", [])


def add_follow_ups_to_campaign(
    *,
    smartlead_campaign_id: int,
    delay_period: int,
    expected_sequence_length: Optional[int] = None,
) -> None:
    sequences = get_campaign_sequences(int(smartlead_campaign_id))

    if (
        expected_sequence_length is not None
        and len(sequences) >= expected_sequence_length
    ):
        return  # nothing to do

    # Build inputs for the original sequences
    original_inputs: List[SmartleadCampaignSequenceInput] = []
    for seq in sequences:
        variants = None
        if seq.sequence_variants:
            variants = [
                SequenceVariantInput(
                    id=v.id,
                    subject=v.subject,
                    email_body=v.email_body,
                    variant_label=v.variant_label,
                    variant_distribution_percentage=v.variant_distribution_percentage,
                )
                for v in seq.sequence_variants
            ]
        original_inputs.append(
            SmartleadCampaignSequenceInput(
                id=seq.id,
                seq_number=seq.seq_number,
                subject=seq.subject,
                email_body=seq.email_body,
                seq_delay_details=SeqDelayDetailsInput(
                    delay_in_days=int(seq.seq_delay_details.delayInDays)
                ),
                seq_variants=variants,
            )
        )

    # Build inputs for the appended follow-up sequences (duplicates)
    clones: List[SmartleadCampaignSequenceInput] = []
    for index, seq in enumerate(sequences):
        # New sequence numbering continues after existing length
        new_seq_number = len(sequences) + index + 1
        # First appended seq uses the provided delay_period; the rest keep their original delay
        new_delay = (
            int(delay_period) if index == 0 else int(seq.seq_delay_details.delayInDays)
        )

        clone_variants = None
        if seq.sequence_variants:
            clone_variants = [
                SequenceVariantInput(
                    id=None,  # new variant ids are unset
                    subject=v.subject,
                    email_body=v.email_body,
                    variant_label=v.variant_label,
                    variant_distribution_percentage=v.variant_distribution_percentage,
                )
                for v in seq.sequence_variants
            ]

        clones.append(
            SmartleadCampaignSequenceInput(
                id=None,  # new sequence id is unset
                seq_number=new_seq_number,
                subject=seq.subject,
                email_body=seq.email_body,
                seq_delay_details=SeqDelayDetailsInput(delay_in_days=new_delay),
                seq_variants=clone_variants,  # can be None
            )
        )

    input_sequences = original_inputs + clones

    try:
        add_sequences_to_campaign(
            campaign_id=int(smartlead_campaign_id),
            input_sequences=input_sequences,
        )
    except Exception as e:
        raise RuntimeError(
            f"Error adding sequences to campaign {smartlead_campaign_id}: {getattr(e, 'message', str(e))}"
        ) from e


# --- 1) Fetch campaigns for selection ---
with st.spinner("Loading campaigns..."):
    if not ss.all_campaigns:
        ss.all_campaigns = get_campaigns()  # expect list of {id, name, ...}

# Build multiselect options as label->id mapping
options = {f"Campaign ID: {c.id}, name: {c.name or ''}": c.id for c in ss.all_campaigns}

# --- 2) Inputs ---
selected_labels = st.multiselect(
    "Select the campaign(s) to add follow-ups",
    options=list(options.keys()),
    default=[
        lbl for lbl in options if options[lbl] in ss.get("selected_campaigns", [])
    ],
    key="campaign_multiselect",
)

ss.selected_campaigns = [options[lbl] for lbl in selected_labels]

ss.delay_period = st.number_input(
    "Enter the delay period before starting the follow-ups",
    min_value=0,
    step=1,
    value=int(ss.get("delay_period", 0)),
    key="delay_period_input",
)

ss.change_follow_up_percentage = st.checkbox(
    "Change follow-up percentage to 90% for any campaign that reached ≥70% sent (or has 0 leads)",
    value=bool(ss.get("change_follow_up_percentage", False)),
    key="change_fu_checkbox",
)

# --- 3) Action Button (flip a flag, then rerun) ---
if st.button("🚀 Add Follow-ups to Selected Campaigns"):
    if not ss.selected_campaigns:
        st.warning("Please select at least one campaign.")
    else:
        ss.successful_campaigns = []
        ss.failed_campaigns = []
        ss.running_add_followups = True
        st.rerun()

# --- 4) Runner block with spinner & progress ---
if ss.running_add_followups:
    total = len(ss.selected_campaigns)
    progress = st.progress(0)
    status = st.empty()

    with st.spinner("Adding follow-ups to campaigns..."):
        for i, cid in enumerate(ss.selected_campaigns, start=1):
            label = next(
                (lbl for lbl, _cid in options.items() if _cid == cid),
                f"Campaign ID: {cid}",
            )
            try:
                # Optional 90% follow-up percentage bump
                if ss.change_follow_up_percentage:
                    stats = get_campaign_statistics(int(cid))
                    # Expect structure similar to TS:
                    # stats["campaign_lead_stats"]["total"], stats["unique_sent_count"]
                    total_leads = int(stats.campaign_lead_stats.total)
                    unique_sent_count = int(stats.unique_sent_count)
                    sent_ratio = (
                        0 if total_leads == 0 else unique_sent_count / total_leads
                    )

                    if total_leads == 0 or sent_ratio >= 0.70:
                        update_smartlead_campaign_follow_up_percentage(
                            campaign_id=int(cid), follow_up_percentage=90
                        )

                # Add follow-ups
                add_follow_ups_to_campaign(
                    smartlead_campaign_id=int(cid),
                    delay_period=int(ss.delay_period),
                )

                ss.successful_campaigns.append(
                    {
                        "Campaign ID": cid,
                        "Campaign Name": label,
                        "Link": f"https://app.smartlead.ai/app/email-campaign/{cid}/analytics",
                        "Error": "N/A",
                    }
                )
            except Exception as e:
                ss.failed_campaigns.append(
                    {
                        "Campaign ID": cid,
                        "Campaign Name": label,
                        "Link": f"https://app.smartlead.ai/app/email-campaign/{cid}/analytics",
                        "Error": str(e) or "Error adding follow-ups",
                    }
                )
            finally:
                status.write(f"Processed {i}/{total}: {label}")
                progress.progress(i / total)

    # Done
    ss.running_add_followups = False

    # --- 5) Output tables ---
    if ss.successful_campaigns:
        st.success("✅ Successfully Added Follow-ups")
        st.dataframe(pd.DataFrame(ss.successful_campaigns), use_container_width=True)

    if ss.failed_campaigns:
        st.error("❌ Failed to Add Follow-ups")
        st.dataframe(pd.DataFrame(ss.failed_campaigns), use_container_width=True)
