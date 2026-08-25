import json
from datetime import datetime

SKILL_BY_LESSON = {
    1: 'Definitions', 2: 'Validity & Soundness', 3: 'Evidence Evaluation',
    4: 'Physics & Information', 5: 'Mathematical Reasoning', 6: 'Falsifiability'
}

def ensure_course_schema(conn):
    conn.executescript('''
    create table if not exists review_state(
      user_id integer not null, question_id integer not null,
      interval_days integer not null default 0, repetitions integer not null default 0,
      ease real not null default 2.5, due_at text, last_correct integer,
      primary key(user_id,question_id));
    create table if not exists debate_attempts(
      id integer primary key,user_id integer not null,lesson_id integer not null,
      initial_position text,initial_confidence integer,steelman text,attack text,
      switched_defense text,final_position text,final_confidence integer,
      completed integer not null default 0,created_at text not null);
    create table if not exists argument_attempts(
      id integer primary key,user_id integer not null,lesson_id integer not null,
      major_text text,minor_text text,conclusion_text text,validity text,
      hidden_assumption text,score integer,created_at text not null);
    create table if not exists experiment_attempts(
      id integer primary key,user_id integer not null,experiment_slug text not null,
      prediction text,observation text,interpretation text,created_at text not null);
    create table if not exists confidence_answers(
      id integer primary key,user_id integer not null,question_id integer not null,
      correct integer not null,confidence integer not null,created_at text not null);
    create table if not exists lab_measurements(
      id integer primary key,user_id integer not null,experiment_slug text not null,
      variable_name text,variable_value real,observed_value real,predicted_value real,
      units text,created_at text not null);
    create table if not exists ela_writing(
      id integer primary key,user_id integer not null,kind text not null,lesson_id integer,
      title text,response text not null,word_count integer not null default 0,created_at text not null);
    create table if not exists source_annotations(
      id integer primary key,user_id integer not null,chapter_id integer not null,
      annotation_type text not null,excerpt text not null,note text,created_at text not null);

    ''')
    conn.commit()

def update_skill(conn,user_id,skill,new_score):
    row=conn.execute('select score from skill_scores where user_id=? and skill=?',(user_id,skill)).fetchone()
    if row:
        blended=round(row[0]*0.65 + new_score*0.35)
        conn.execute('update skill_scores set score=? where user_id=? and skill=?',(blended,user_id,skill))
    else:
        conn.execute('insert into skill_scores(user_id,skill,score) values(?,?,?)',(user_id,skill,new_score))

def schedule_review(conn,user_id,question_id,correct):
    now=datetime.utcnow()
    row=conn.execute('select * from review_state where user_id=? and question_id=?',(user_id,question_id)).fetchone()
    reps=(row['repetitions'] if row else 0)
    interval=(row['interval_days'] if row else 0)
    ease=(row['ease'] if row else 2.5)
    if correct:
        reps += 1
        if reps == 1: interval=1
        elif reps == 2: interval=3
        else: interval=max(7, round(max(1,interval)*ease))
        ease=min(3.0,ease+0.05)
    else:
        reps=0; interval=1; ease=max(1.3,ease-0.2)
    from datetime import timedelta
    due=(now+timedelta(days=interval)).isoformat()
    conn.execute('''insert into review_state(user_id,question_id,interval_days,repetitions,ease,due_at,last_correct)
      values(?,?,?,?,?,?,?) on conflict(user_id,question_id) do update set interval_days=excluded.interval_days,
      repetitions=excluded.repetitions,ease=excluded.ease,due_at=excluded.due_at,last_correct=excluded.last_correct''',
      (user_id,question_id,interval,reps,ease,due,int(correct)))

DIAGNOSTIC_SEED = [
 ('ELA','Which sentence states a claim rather than evidence?', ['The pendulum took 2.1 seconds.','Longer pendulums have longer periods.','We repeated the trial three times.','The ruler measured 1 meter.'], 'Longer pendulums have longer periods.'),
 ('ELA','Which sentence best uses evidence?', ['I think it is true.','The data table shows the period increased as length increased.','Everyone knows this.','It sounds correct.'], 'The data table shows the period increased as length increased.'),
 ('Logic','All mammals breathe air. Whales are mammals. What follows?', ['Whales breathe air.','All air-breathers are whales.','Whales are fish.','Nothing follows.'], 'Whales breathe air.'),
 ('Logic','A valid argument is one in which...', ['the conclusion follows from the premises','every premise is definitely true','the speaker wins','the conclusion is popular'], 'the conclusion follows from the premises'),
 ('Logic','Which is a counterexample to “All objects that fly are birds”?', ['an eagle','a sparrow','an airplane','a feather'], 'an airplane'),
 ('Physics','If pendulum length increases while gravity stays the same, its period generally...', ['increases','decreases','becomes zero','must stay identical'], 'increases'),
 ('Physics','Which is an observation?', ['The longer string caused the slower swing.','The measured period was 2.8 seconds.','Gravity explains the pattern.','The theory is correct.'], 'The measured period was 2.8 seconds.'),
 ('Physics','In an experiment, the variable deliberately changed is the...', ['independent variable','dependent variable','conclusion','constant result'], 'independent variable'),
 ('Math','If a period is 2 seconds, its frequency is...', ['0.5 Hz','2 Hz','4 Hz','0 Hz'], '0.5 Hz'),
 ('Math','Which graph axis normally contains the independent variable?', ['x-axis','y-axis only','neither axis','the title'], 'x-axis'),
 ('Math','If three trials are 2.0, 2.2, and 2.1 seconds, the mean is...', ['2.1 s','6.3 s','2.0 s','3.1 s'], '2.1 s'),
 ('ELA','Which is the strongest conclusion?', ['Therefore the data support the proposition within the conditions tested.','Therefore I am right.','Obviously this proves everything.','My opponent is wrong.'], 'Therefore the data support the proposition within the conditions tested.'),
]

VOCAB_SEED = [
 ('proposition','A statement put forward for consideration or argument.','Logic'),
 ('premise','A statement offered as support for a conclusion.','Logic'),
 ('conclusion','The statement an argument claims follows from its premises.','Logic'),
 ('validity','Whether a conclusion logically follows from the premises.','Logic'),
 ('soundness','Validity plus true or well-supported premises.','Logic'),
 ('evidence','Information used to support or challenge a claim.','ELA'),
 ('inference','A conclusion reached from evidence or premises.','ELA'),
 ('falsifiable','Capable in principle of being shown false by some observation.','Science'),
 ('independent variable','The factor deliberately changed in an experiment.','Physics'),
 ('dependent variable','The factor measured as a response.','Physics'),
 ('decoherence','Loss of observable quantum interference through interaction with an environment.','Physics'),
 ('causation','A relationship in which a change in one factor produces a change in another.','Science'),
]

def ensure_autograde_schema(conn):
    conn.executescript('''
    create table if not exists diagnostic_questions(
      id integer primary key,domain text not null,prompt text not null,
      options_json text not null,correct_answer text not null);
    create table if not exists diagnostic_attempts(
      id integer primary key,user_id integer not null,total_score integer not null,
      domain_scores_json text not null,created_at text not null);
    create table if not exists vocabulary_terms(
      id integer primary key,term text unique not null,definition text not null,domain text not null);
    create table if not exists vocabulary_review(
      user_id integer not null,term_id integer not null,correct_count integer not null default 0,
      incorrect_count integer not null default 0,due_at text,last_result integer,
      primary key(user_id,term_id));
    create table if not exists evidence_locker(
      id integer primary key,user_id integer not null,title text not null,claim_side text not null,
      source_type text not null,citation text not null,evidence_text text not null,
      relevance_note text not null,quality_score integer not null default 0,created_at text not null);
    create table if not exists writing_submissions(
      id integer primary key,user_id integer not null,title text not null,kind text not null,
      stage text not null,response text not null,word_count integer not null,
      citation_count integer not null default 0,auto_score integer not null,
      rubric_json text not null,created_at text not null);
    create table if not exists competency_events(
      id integer primary key,user_id integer not null,subject text not null,skill text not null,
      points integer not null,source text,created_at text not null);
    ''')
    if conn.execute('select count(*) from diagnostic_questions').fetchone()[0] == 0:
        for domain,prompt,opts,correct in DIAGNOSTIC_SEED:
            conn.execute('insert into diagnostic_questions(domain,prompt,options_json,correct_answer) values(?,?,?,?)',
                         (domain,prompt,json.dumps(opts),correct))
    for term,definition,domain in VOCAB_SEED:
        conn.execute('insert or ignore into vocabulary_terms(term,definition,domain) values(?,?,?)',(term,definition,domain))
    conn.commit()

def award_competency(conn,user_id,subject,skill,points,source=''):
    conn.execute('insert into competency_events(user_id,subject,skill,points,source,created_at) values(?,?,?,?,?,?)',
                 (user_id,subject,skill,int(points),source,datetime.utcnow().isoformat()))
