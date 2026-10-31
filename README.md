# Provenance Guard

> ### 👋 Start here
>
> **New to this repo? Read [RUNNING.md](RUNNING.md) first.**
>
> Once `python test.py` passes, in one terminal:
>
> ```bash
> python app.py
> ```
>
> and in another:
>
> ```bash
> curl -X POST http://127.0.0.1:5000/ping \
>   -H "Content-Type: application/json" \
>   -d '{"message": "hello"}'
> ```
>
> That's a web service. Something sent it text and it sent something back.
> Everything this unit is filling in the middle.
>
> **The rest of this file is your submission.** Fill it in as you go.

---

<!-- ─────────────────────────────────────────────────────────────────────────
     Unit 7 asks for the first five sections. Unit 8 adds the five below.

     Everything is pasted as TEXT. A pasted curl response gets full credit;
     a picture of your terminal gets none.
     ───────────────────────────────────────────────────────────────────────── -->

<!-- ═══════════════════════ UNIT 7 — THE BUILD ═══════════════════════ -->

## What This Does

<!-- The path a submission takes, from arriving to the label a reader sees.
     Six or seven steps — this is the trace you wrote in Milestone 1. -->

Steps:
1. Request arrives at server (app.py)
2. Submit Function is called
3. Signal one is GPT-2 adding a model_score using detector.py
4. Signal two is style_score using stylometry.py
5. We combine the two signals at next step
6. We add a guess using score_to_label function in scoring.py
7. audit.py adds a permanent record with content_id

---

## Signals and Scoring

<!-- For each signal: what property it measures, why that might differ between
     human and AI writing, and WHAT IT CAN'T SEE.

     The blind spot is not optional. If you can't name it you don't understand
     the signal yet — and unit 8's attack set is built out of blind spots. -->

### Signal one — the model signal

**What it measures:** It measures how predictable the text is to GPT-2

**Why that might differ between human and AI writing:**
GPT-2 checks the text and calculates a perplexity score. If it can predict the writing easily - then it is AI-like, if not then it is more human like. Lower perplexity means high chance of AI written.

**What it can't see:**
Predictable does not always mean AI-written. A simple writing style could be used by many humans. Also if a prose is full of fancy jargon words, it would be treated as human written, even when AI might have written that.

### Signal two — the style signal

**What it measures:** It measures the shape of the text. Three measures are - sentence_length_spread, type_token_ratio and punctuation_density

| Measure | What it computes | Weight |
|---|---|---|
| `sentence_length_spread` | stdev ÷ mean of words per sentence. Low spread reads as AI | 0.6 |
| `punctuation_density` | `, ; : — – ( ) ! ?` and quotes per word (full stops left out). Little punctuation reads as AI, capped at 0.75 so it can't call plain writing AI on its own | 0.4 |
| `type_token_ratio` | unique words ÷ total words | 0 (measured, not counted) |

Each measure is flipped and scaled onto 0–1 (1.0 = most AI-like), then
averaged with the weights above. Under two sentences, spread counts as 0.5,
because there's nothing to measure.

**Why type-token ratio is weighted 0:** on my calibration texts it ran
backwards. The AI paragraphs had *more* varied vocabulary (0.86) than the plain
human one (0.79), so counting it would have pushed plain writers toward "AI".

**Why that might differ between human and AI writing:**
human writing is lumpy. A three-word sentence can sit next to a forty-word one. AI writing tends to march along evenly.

**What it can't see:**
it can't read. Anything that changes the shape without changing the content moves the score: adding typos, chopping up sentences, pasting in a quote. That's a cheap trick to pull on purpose, and the Unit 8 attacks will use it.

### The combining rule

<!-- Write the rule in words, then give the numbers. What happens when the two
     signals disagree? -->

**The rule:** an average, but leaning toward whichever signal says human.

**The numbers:** an equal-weight average, pulled toward the more human signal
when the two disagree.

```
average = 0.5 × model_score + 0.5 × style_score

if |model_score − style_score| ≤ 0.3:      # they agree
    final_score = average
else:                                      # they disagree
    final_score = (average + min(model_score, style_score)) / 2
```

- `WEIGHT_MODEL_SIGNAL = 0.5`, `WEIGHT_STYLE_SIGNAL = 0.5`, `DISAGREEMENT_GAP = 0.3` (in `config.py`)
- Both inputs and the output run 0.0 (human) to 1.0 (AI)
- Label thresholds: below `0.35` → human, `0.35 – 0.65` → unsure, above `0.65` → AI


**Where it lives:** `scoring.py::combine_signals`

<!-- ⚠️ The grader checks your code against that line. If your rule lives
     somewhere else, say where. -->

**A case where my two signals split, and what my rule does with it:**

*Example:*

| | model_score | style_score | final_score | Label |
|---|---|---|---|---|
| Signals agree (AI) | 0.90 | 0.80 | gap 0.10, so average = **0.85** | high-confidence AI |
| Signals agree (human) | 0.20 | 0.10 | gap 0.10, so average = **0.15** | high-confidence human |
| Signals split | 0.90 | 0.10 | gap 0.80, so (0.50 + 0.10) / 2 = **0.30** | high-confidence human |

When the signals split, the score is pulled toward the one that reads the text
as more human. A wrong accusation costs a writer more than a missed AI text
costs the site, so when my two methods disagree, the doubt goes to the writer.

*A real split* — a human answer from the HC3 dataset (Reddit, "If salt is bad
for cars, why use it on roads?"):

> salt is good for not dying in car crashes and car crashes are worse for cars
> then salt. Some places use other things, but salt is really cheap compared to
> most alternatives, although sand is pretty good.

| model_score | style_score | gap | plain average | my rule | Label |
|---|---|---|---|---|---|
| 0.404 | 0.792 | 0.39 | 0.598 | (0.598 + 0.404) / 2 = **0.501** | unsure |

Signal one reads it as human: casual wording and a spelling slip ("then" for
"than") are hard for GPT-2 to predict. Signal two reads it as AI, because it's
only two sentences of similar length with little punctuation, so there's no
lumpiness to see. The gap is over 0.3, so my rule leans toward signal one and
pulls the score from 0.60 down to 0.50, the middle of the unsure band. It still
isn't called human. That's a fair outcome for two sentences, which is too
little text for either signal to be sure of.

*What the rule can't fix:* the human answer to "how does a dredge work?" is
written in an encyclopedia style and scores 0.777 / 0.623. Both signals wrongly
agree it looks AI, the gap is only 0.15, so the rule doesn't step in, and it's
labelled high-confidence AI (0.70). Leaning toward human only helps when one
signal gets it right.

---

## Label Variants

<!-- The exact text of all three labels, as a reader would see them, and the
     score range each covers.

     Write them for someone who has never heard the word "threshold". -->

| Label | Score range | The exact text a reader sees |
|---|---|---|
| high-confidence human | 0.00 – 0.35 | "This reads like it was written by a person. Our checks found the patterns we usually see in human writing." |
| unsure | above 0.35, below 0.65 | "We can't tell either way. Our checks gave mixed results, which happens often with clear, simple writing. This is not a finding that AI was used. If you wrote this yourself, you can ask for a review." |
| high-confidence AI | 0.65 – 1.00 | "This reads like it was likely written with an AI tool. Both of our checks pointed that way. Automated checks can be wrong, so if you wrote this yourself, you can ask for a review." |

**Where it lives:** `scoring.py::score_to_label`, with the two cut-offs in
`config.py` (`HUMAN_THRESHOLD = 0.35`, `AI_THRESHOLD = 0.65`). `/submit` puts
the label text in its response and in the audit log.

**All three are reachable.** Real texts run through the service:

| Text | model_score | style_score | final_score | Label |
|---|---|---|---|---|
| Casual note: *"Ugh. My landlord texted at 6am — again! — about the 'noise' from my kettle…"* | 0.3202 | 0.0000 | **0.0800** | high-confidence human |
| HC3 Reddit answer about salt on roads (from the combining-rule section) | 0.4044 | 0.7918 | **0.5012** | unsure |
| Even, generic prose: *"Artificial intelligence is transforming the way businesses operate…"* | 0.8634 | 0.6226 | **0.7430** | high-confidence AI |

*Example:* using the scores from the combining rule above, a submission
scoring **0.85** sees the AI label, **0.15** sees the human label, and **0.50**
(the signals split) sees the unsure label.

**Why I worded the "unsure" one this way:**
<!-- It's the hardest of the three. It has to admit uncertainty without
     sounding like an accusation, because the person reading it may well have
     written every word themselves. -->

The person reading "unsure" may well have written every word themselves, and
plain, simple writing is exactly what pushes signal one toward "AI". So the
label:

- **Says plainly that it isn't an accusation.** "This is not a finding that AI
  was used" closes off the reading a worried writer jumps to first.
- **Explains why without blaming the writer.** "Mixed results, which happens
  often with clear, simple writing" puts the uncertainty on the tool, not on
  how the person writes.
- **Gives them something to do.** Pointing to a review gives the writer a
  next step instead of leaving them stuck with a vague result.
- **Avoids numbers and jargon.** No scores, no "threshold", no "confidence
  0.52". A reader can't do anything useful with a number.


---

## Sample Run

<!-- One submission and one appeal, pasted as text: the request, the response,
     and the log entries. -->

**A submission**

<!-- The response needs content_id, guess, confidence, label, AND both
     signal scores - model_score and style_score. Unit 8's tools read those
     two off the response, so leaving them out costs you next unit's
     diagnostics. -->

The human-written HC3 answer from the combining-rule section — the case where
my two signals split.

```bash
$ curl -X POST http://127.0.0.1:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "salt is good for not dying in car crashes and car crashes are worse for cars then salt. Some places use other things, but salt is really cheap compared to most alternatives, although sand is pretty good.", "creator_id": "divi-259"}'
```

```json
{
    "combined_score": 0.5012,
    "confidence": 0.0024,
    "content_id": "9ac95395-2560-4199-821d-fc08bd2d9230",
    "guess": "unsure",
    "label": "We can't tell either way. Our checks gave mixed results, which happens often with clear, simple writing. This is not a finding that AI was used. If you wrote this yourself, you can ask for a review.",
    "model_score": 0.4044,
    "style_score": 0.7918
}
```

`confidence` is how far the score sits from a coin flip: `|final_score − 0.5| × 2`,
so 0.0 at 0.50 and 1.0 at either end. This one is 0.0024 — the service is
saying, correctly, that it has no idea.

**An appeal**

```bash
$ curl -X POST http://127.0.0.1:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "9ac95395-2560-4199-821d-fc08bd2d9230", "reasoning": "I wrote this myself. The then/than slip is mine, not a model'\''s."}'
```

```json
{
    "content_id": "9ac95395-2560-4199-821d-fc08bd2d9230",
    "message": "Thanks. A person will review this submission. Nothing changes until they do.",
    "ok": true,
    "status": "under_review"
}
```

A mistyped id doesn't fail silently — it gets a 404:

```bash
$ curl -X POST http://127.0.0.1:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "not-a-real-id", "reasoning": "x"}'
```

```json
{"error": "unknown_content_id", "message": "We couldn't find a submission with that id."}
```

**What the log shows afterwards**

```bash
$ curl "http://127.0.0.1:5000/log?limit=3"
```

```json
{
    "count": 3,
    "entries": [
        {
            "combined_score": 0.5012,
            "content_id": "ecb3860d-c873-4940-9702-b9fdac403687",
            "creator_id": "me",
            "guess": "unsure",
            "label": null,
            "model_score": 0.4044,
            "status": "decided",
            "style_score": 0.7918,
            "timestamp": "2026-10-29T00:32:16+00:00"
        },
        {
            "combined_score": 0.5012,
            "content_id": "9ac95395-2560-4199-821d-fc08bd2d9230",
            "creator_id": "divi-259",
            "guess": "unsure",
            "label": "We can't tell either way. Our checks gave mixed results, which happens often with clear, simple writing. This is not a finding that AI was used. If you wrote this yourself, you can ask for a review.",
            "model_score": 0.4044,
            "status": "decided",
            "style_score": 0.7918,
            "timestamp": "2026-10-31T02:40:14+00:00"
        },
        {
            "content_id": "9ac95395-2560-4199-821d-fc08bd2d9230",
            "creator_id": "divi-259",
            "event": "appeal",
            "reasoning": "I wrote this myself. The then/than slip is mine, not a model's.",
            "status": "under_review",
            "timestamp": "2026-10-31T02:40:33+00:00"
        }
    ]
}
```

The first entry is the same text sent during Milestone 4, before labels
existed (`label: null`). The appeal sits *after* the original decision instead
of overwriting it: the log keeps what was decided, that it was challenged, and
in what order.

---

## How I Used AI

**Moment 1**

- *What I asked for:* I asked Claude Code to format README.
- *What came back:* It helped me with the words and formatting
- *What I changed:* I updated the doc

**Moment 2**

- *What I asked for:* to critique the criteria
- *What came back:* It critiqued the why behind third and fouth criteria
- *What I changed:* I updated my criteria accordingly

<!-- ═══════════════════════ UNIT 8 — THE TEST ═══════════════════════ -->

---

## Rate Limiting

**My limits:** ___ per minute, ___ per day

**Why those numbers and not others:**
<!-- Think about two people: a real writer submitting their own work a few
     times an hour, and a script sending a thousand variations to map your
     thresholds. Your numbers have to be liveable for the first and hostile to
     the second. -->

**What a caller counts as:** <!-- per address, or per creator_id? They fail
differently — one script can look like a thousand callers, and one household
can look like one. -->

**The run of status codes when I pushed past it:**

<!-- python run_attacks.py --flood 15 -->

```

```

---

## Attack Run — Before

<!-- Every attack with its outcome and a held-or-broke mark.
     `run_attacks.py --label before` produces the table. -->



**Ten audit log entries from the run**

<!-- Choose entries that show the interesting failures, not the ten easiest. -->

```json

```

**The single worst outcome** — the one I'd least want to explain to a writer
whose work got caught by it:



---

## Run Log and Verdicts

<!-- Your five criteria across three trials. `run_eval.py --label before`. -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |
| 2.  |  |  |  |  |  |
| 3.  |  |  |  |  |  |
| 4.  |  |  |  |  |  |
| 5.  |  |  |  |  |  |

**Real output from one trial**, pasted as text, naming the file and function
that produced it:

```json

```

**Diagnoses**

<!-- For each miss AND each broken attack: the stage and the mechanism.

     Your service has five stages: the route, signal one, signal two, the
     combining rule, and the label mapping.

     Not a diagnosis:  "The evasion attacks got through."
     A diagnosis:      "Four evasion inputs got through. All four had typos
                        added to AI-generated text. My second signal measures
                        word variety, and typos raise word variety — so it read
                        them as more human. My combining rule weights that
                        signal at 0.6, so it dragged the whole score down."

     Look for a pattern. Five failures on one signal is one problem, not five. -->



---

## The Improvement

**What I changed:**

**Which diagnosis pointed at it:**

### Attack Run — After

<!-- Same format. `run_attacks.py --label after` -->



**Did it help, and how do I know:**

<!-- Widening the unsure band usually fixes one problem and creates another.
     Reporting that trade honestly is worth full credit. -->



---

## What's Still Broken

<!-- For each attack still getting through and each criterion still missed:
     what you'd do, and why you stopped. -->



**The trade I'd make if this ran for real:**

<!-- Two sentences. Fewer wrong accusations means more AI text getting through.
     Say which way you'd go and WHO PAYS FOR IT. -->



<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 7

       [ ] criteria.md has five numbered criteria, each naming a target
       [ ] Each has a reason underneath
       [ ] POST /submit returns content_id, guess, confidence, label,
           model_score and style_score
       [ ] Two signals that measure DIFFERENT things, each with a named blind spot
       [ ] Three label variants, all reachable, written out in full
       [ ] POST /appeal changes status and writes to the log
       [ ] Signals and Scoring names scoring.py::combine_signals
       [ ] Sample Run: a submission AND an appeal, as pasted text
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN

     SUBMISSION CHECKLIST — unit 8

       [ ] Rate limiting on /submit, with your numbers justified
       [ ] The pasted run of status codes showing 429
       [ ] Audit log with all nine fields, recording rejections too
       [ ] The attack set run IN FULL, every input with an outcome
       [ ] Ten audit log entries pasted as text
       [ ] Five criteria across three trials
       [ ] A diagnosis for every miss and every broken attack — stage AND mechanism
       [ ] One improvement, with Attack Run — After
       [ ] What's Still Broken, including the production trade
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
