from openai import OpenAI
import csv
import io
import streamlit as st


def get_gpt_answer(system_prompt, user_prompt, temperature=0.7):
    openAIClient = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    response = openAIClient.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip().lower()


# ---------------------- Helper Functions ----------------------


def csv_to_json(file_content):
    return list(csv.DictReader(io.StringIO(file_content.decode("utf-8"))))


def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]
