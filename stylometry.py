"""
Signal two: the style signal. ← YOU BUILD THIS IN MILESTONE 4

Signal one reads the text for meaning. This one measures it *as text* — the
shape of it, without understanding a word.

Three measures are stubbed below because the brief names those three. They are
stubs, not implementations: what they compute is yours, and so is how you
combine them.

    sentence_length_spread   do sentences vary in length, or march in step?
    type_token_ratio         how much of the vocabulary repeats?
    punctuation_density      how much punctuation, and how varied?

Why these might differ between human and AI writing: generated prose tends
toward even, mid-length sentences and a narrower band of vocabulary, because
that's what "most likely next word" produces on average. Human writing is
lumpier — a three-word sentence next to a forty-word one.

⚠️ **The blind spot, which you have to name in Milestone 1.**

This signal cannot read. It has no idea what the text says. Anything that
changes the shape without changing the substance moves it — adding typos,
breaking up sentences, pasting in a quotation. That is a very cheap thing for
someone to do on purpose, and unit 8's attack set will do it to you.

Build each function on its own and call it from a terminal before you wire
anything together:

    python stylometry.py "some text to look at"
"""

import re
import statistics


def sentences(text: str) -> list[str]:
    """Split into sentences. Rough and good enough — given to you."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def words(text: str) -> list[str]:
    """Split into lowercase words, punctuation stripped. Given to you."""
    return re.findall(r"[a-z0-9']+", text.lower())


# ── The three measures — YOU BUILD THESE ─────────────────────────────────────

def sentence_length_spread(text: str) -> float:
    """
    How much sentence length varies. ← TODO

    Returns:
        A float. Decide yourself what scale it's on and which direction means
        "more human" — then write that down, because your combining rule
        depends on knowing it.

    A hint on what you're reaching for: the standard deviation of sentence
    lengths, probably divided by the mean so a long text and a short one are
    comparable. `statistics.stdev` is imported for you.

    Watch the edge case: a one-sentence submission has no spread at all, and
    `stdev` raises on fewer than two values. Decide what that should return
    before the attack set decides for you.

    the coefficient of variation (stdev ÷ mean) of words per sentence.
    0.0 means every sentence is the same length; higher means lumpier, which
    reads as more human. Fewer than two sentences returns 0.0, and
    `style_signal` treats that as "no evidence" rather than "very AI".
    """
    lengths = [len(words(s)) for s in sentences(text)]
    lengths = [n for n in lengths if n > 0]
    if len(lengths) < 2:
        return 0.0
    return round(statistics.stdev(lengths) / statistics.mean(lengths), 4)


def type_token_ratio(text: str) -> float:
    """
    Unique words over total words. ← TODO

    Returns:
        A float between 0 and 1. Higher means more varied vocabulary.

    Worth knowing before you rely on it: this measure falls as text gets
    longer, because common words repeat. Two texts of different lengths aren't
    directly comparable on it, and if your test inputs vary a lot in length,
    that alone can look like a signal.
    """
    tokens = words(text)
    if not tokens:
        return 0.0
    return round(len(set(tokens)) / len(tokens), 4)


def punctuation_density(text: str) -> float:
    """
    How much punctuation, relative to length. ← TODO

    Returns:
        A float. Whether you count all punctuation or only some kinds — commas,
        semicolons, dashes — is a real choice. Semicolons and em dashes are
        more interesting than full stops, because they vary more between
        writers.

    the "expressive" marks — , ; : — – ( ) ! ? and quotes — per word.
    Full stops are left out because every sentence has one, so they mostly
    measure sentence length again.
    """
    tokens = words(text)
    if not tokens:
        return 0.0
    marks = len(re.findall(r"[,;:!?()\"\u2014\u2013\u201c\u201d]|--", text))
    return round(marks / len(tokens), 4)


# ── Combining them ───────────────────────────────────────────────────────────

def style_signal(text: str) -> float:
    """
    The style signal as a 0–1 score. **Higher means more likely AI.** ← TODO

    Combine your three measures into one number. Same direction as
    `detector.model_signal`, so that `scoring.combine_signals` can treat them
    the same way — if one of your signals runs backwards, everything above it
    is wrong in a way that's hard to see.

    Two things to decide and write down:

      1. Which direction each measure points. Low spread means more AI-ish, so
         it needs flipping. Work out which of your three need that.
      2. How to get each onto a comparable scale. A raw type-token ratio sits
         between 0 and 1; a raw punctuation count doesn't. Adding them
         unscaled means whichever has the bigger numbers wins by default.

    Test it on the four calibration inputs from Milestone 4 — clearly AI,
    clearly human, plain conventional human writing, lightly-edited AI — before
    you trust it. Plain and ordinary, not formal: formal prose reads as *human*
    to signal one, and it is plain writing that gets accused.

    with the numbers in the constants below:

      - Spread is flipped: a coefficient of variation of 0.1 or less scores
        1.0 (AI-ish), 0.9 or more scores 0.0, straight line between. Under two
        sentences there's nothing to measure, so it counts as 0.5.
      - Punctuation is flipped too: no expressive marks scores 0.75, 0.15 or
        more per word scores 0.0. It tops out at 0.75 rather than 1.0 because
        plain writers use little punctuation and I don't want that alone to
        read as AI.
      - Type-token ratio is measured but weighted 0. On my calibration texts
        it ran backwards: the AI paragraphs had MORE varied vocabulary than
        the plain human one, so counting it would push plain writers toward
        "AI" — the exact false positive this project is about.
    """
    tokens = words(text)
    if not tokens:
        return 0.5

    if len(sentences(text)) < 2:
        spread_ai = 0.5
    else:
        spread = sentence_length_spread(text)
        spread_ai = _scale(spread, SPREAD_MOST_AI, SPREAD_MOST_HUMAN)

    punct_ai = PUNCT_CEILING * _scale(punctuation_density(text), 0.0, PUNCT_MOST_HUMAN)
    ttr_ai = _scale(type_token_ratio(text), TTR_MOST_AI, TTR_MOST_HUMAN)

    score = (
        WEIGHT_SPREAD * spread_ai
        + WEIGHT_PUNCT * punct_ai
        + WEIGHT_TTR * ttr_ai
    ) / (WEIGHT_SPREAD + WEIGHT_PUNCT + WEIGHT_TTR)
    return round(min(max(score, 0.0), 1.0), 4)


# Where each measure sits at its most AI-like and most human-like. Anything
# past either end is clamped. Taken from my calibration texts — move them when
# you have better ones.
SPREAD_MOST_AI, SPREAD_MOST_HUMAN = 0.1, 0.9
PUNCT_MOST_HUMAN = 0.15
PUNCT_CEILING = 0.75
TTR_MOST_AI, TTR_MOST_HUMAN = 0.6, 0.9

WEIGHT_SPREAD = 0.6
WEIGHT_PUNCT = 0.4
WEIGHT_TTR = 0.0


def _scale(value: float, most_ai: float, most_human: float) -> float:
    """Map a raw measure onto 0–1 where 1.0 is most AI-like, clamped."""
    position = (value - most_ai) / (most_human - most_ai)
    return min(max(1.0 - position, 0.0), 1.0)


if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or (
        "The system works well. It handles most cases correctly and provides "
        "good results. Users generally find it easy to use and understand."
    )

    print(f"{len(sentences(text))} sentences, {len(words(text))} words\n")
    print(f"sentence_length_spread   {sentence_length_spread(text)}")
    print(f"type_token_ratio         {type_token_ratio(text)}")
    print(f"punctuation_density      {punctuation_density(text)}")
    print(f"style_signal             {style_signal(text)}   (higher = more likely AI)")
