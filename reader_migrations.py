import json
import sqlite3

STARTER_CHECKS = {
    'On Things Said Without Combination': [
        ('Which is one of Aristotle’s categories named in this selection?', ['Substance','Simulation','Algorithm','Photon'], 'Substance', 'Aristotle lists substance among the categories.'),
        ('Why define categories before debate?', ['To keep key terms stable','To guarantee agreement','To avoid evidence','To choose a winner'], 'To keep key terms stable', 'Stable terms make later inferences testable.'),
    ],
    'On Substance and Predication': [
        ('In “Reality is informational,” what is the subject?', ['Reality','Informational','Is','Argument'], 'Reality', 'Reality is the thing about which something is predicated.'),
        ('Before evaluating a proposition, the predicate should be:', ['Clarified','Hidden','Changed mid-debate','Ignored'], 'Clarified', 'The debaters need to know what the predicate means.'),
    ],
    'Ideas and Perception': [
        ('Which distinction is central to this reading exercise?', ['Observation vs interpretation','Winner vs loser','Popular vs unpopular','Long vs short'], 'Observation vs interpretation', 'The exercise separates what is observed from what is inferred.'),
        ('A detector result is best classified first as:', ['Observation','Metaphysical proof','Fallacy','Definition'], 'Observation', 'Interpretation comes after the recorded observation.'),
    ],
    'What Does It Mean To Exist?': [
        ('Which term most needs an agreed definition in this section?', ['Existence','Score','Animation','Password'], 'Existence', 'The debate turns on what “exists” and “independently” mean.'),
        ('Agreeing on a definition means agreeing that the proposition is true.', ['True','False'], 'False', 'Definitions can be shared while conclusions remain disputed.'),
    ],
    'Cause and Effect': [
        ('A causal inference goes beyond:', ['The immediate observation','All language','Every experiment','Any premise'], 'The immediate observation', 'Causal reasoning connects observations to claims about what produces them.'),
        ('A good causal analysis should consider:', ['Alternative explanations','Only the preferred theory','Popularity','Personal attacks'], 'Alternative explanations', 'Alternatives help test whether causation is uniquely supported.'),
    ],
    'Skeptical Discipline': [
        ('The skeptical method asks us to:', ['Limit conclusions to what evidence supports','Reject all knowledge','Believe every possibility','Avoid definitions'], 'Limit conclusions to what evidence supports', 'Skepticism here disciplines how far inference may extend.'),
        ('“Possible” and “established by evidence” mean the same thing.', ['True','False'], 'False', 'Logical possibility is much weaker than empirical support.'),
    ],
}


def ensure_reader_schema(conn: sqlite3.Connection):
    conn.executescript('''
    create table if not exists reading_questions(
        id integer primary key,
        chapter_id integer not null,
        prompt text not null,
        options_json text not null,
        correct_answer text not null,
        explanation text default ''
    );
    create table if not exists reading_attempts(
        id integer primary key,
        user_id integer not null,
        chapter_id integer not null,
        score integer not null,
        created_at text not null
    );
    create table if not exists bookmarks(
        user_id integer not null,
        chapter_id integer not null,
        created_at text not null,
        primary key(user_id, chapter_id)
    );
    ''')
    cols = {r[1] for r in conn.execute('pragma table_info(books)').fetchall()}
    if 'is_full_text' not in cols:
        conn.execute("alter table books add column is_full_text integer not null default 0")
    if 'source_url' not in cols:
        conn.execute("alter table books add column source_url text default ''")
    if 'reading_level' not in cols:
        conn.execute("alter table books add column reading_level text default ''")

    # Seed reading checks for the starter library without duplicating them.
    for title, checks in STARTER_CHECKS.items():
        chapter = conn.execute('select id from chapters where title=?', (title,)).fetchone()
        if not chapter:
            continue
        chapter_id = chapter[0]
        if conn.execute('select 1 from reading_questions where chapter_id=? limit 1', (chapter_id,)).fetchone():
            continue
        for prompt, options, correct, explanation in checks:
            conn.execute('insert into reading_questions(chapter_id,prompt,options_json,correct_answer,explanation) values(?,?,?,?,?)',
                         (chapter_id, prompt, json.dumps(options), correct, explanation))
    conn.commit()
