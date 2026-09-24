from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

import time

from core.llm import get_llm, invoke_with_retry


def split_transcript(transcript: str) -> list:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=3000,
        chunk_overlap=200
    )
    return splitter.split_text(transcript)


def summarize(transcript: str) -> str:
    llm = get_llm()

    map_prompt = ChatPromptTemplate.from_messages([
        ("system", "Summarize this portion of a meeting transcript concisely."),
        ("human", "{text}"),
    ])

    map_chain = map_prompt | llm | StrOutputParser()

    chunks = split_transcript(transcript)
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(0.8)  # light pacing between chunk calls to avoid tripping Groq's rate limit
        chunk_summaries.append(invoke_with_retry(map_chain, {"text": chunk}))

    # Bug fix: this used to always make a second "combine" LLM call even
    # when there was only ONE chunk (the common case -- most videos'
    # transcripts fit in a single ~3000-char chunk), doubling API calls,
    # latency, and rate-limit usage for no benefit, since combining a single
    # summary with itself changes nothing about the content. core/extractor.py
    # right next to this file already has exactly this short-circuit for its
    # own map-reduce calls; this brings summarize() in line with it. Only
    # when a transcript is long enough to actually split into multiple
    # chunks does the extra combine step still run.
    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    combined = "\n\n".join(chunk_summaries)

    combined_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert meeting summarizer. Combine these partial summaries "
            "into one final professional meeting summary in bullet points.",
        ),
        ("human", "{text}"),
    ])

    combined_chain = (
        RunnablePassthrough() | RunnableLambda(lambda x: {"text": x}) | combined_prompt | llm | StrOutputParser()
    )

    return invoke_with_retry(combined_chain, combined)


def generate_title(transcript: str) -> str:
    llm = get_llm()

    title_chain = (
        RunnablePassthrough() | RunnableLambda(lambda x: {"text": x}) |
        ChatPromptTemplate.from_messages([
            (
                "system",
                "Based on the meeting transcript, generate a short professional meeting title "
                "(max 8 words). The title MUST be written in English, regardless of what "
                "language the transcript itself is in. Only return the title, nothing else.",
            ),
            ("human", "{text}"),
        ])
        | llm
        | StrOutputParser()
    )

    return invoke_with_retry(title_chain, transcript[:2000])