/**
 * Behavioural Blueprint Assessment (designed by Sylvia Lyne Njoki)
 * Google Form + Sheet builder with automatic scoring and emailed results.
 *
 * HOW TO USE
 * 1. Go to https://script.google.com and click "New project".
 * 2. Delete the sample code, paste this whole file, and click Save.
 * 3. Optional: put the coach's email in COACH_EMAIL below to get a copy of every result.
 * 4. Choose the function "setup" in the toolbar and click Run. Approve the permissions.
 * 5. Open "Execution log": it prints the Form link (to share), the edit link and the Sheet link.
 *
 * What gets created
 * - A Google Form: intro page, Sections A to D (8 statements each, 1 to 5 scale),
 *   a reflection page (tick any endings, plus "Other" for free text) and the closing message.
 * - A linked Google Sheet with the raw responses, a "Scores" tab (one row per person)
 *   and a "Dashboard" tab with group averages, dominant-style counts and two charts.
 * - A submit trigger that scores each response, writes it to "Scores" and emails
 *   the respondent (if they gave an email) a results summary with bar chart.
 */

// ---------- Settings ----------
const COACH_EMAIL = '';          // e.g. 'coach@example.com'  (leave empty for no copy)
const FORM_TITLE = 'Behavioural Blueprint Assessment';

// ---------- Content ----------
const SECTIONS = [
  { key: 'A', style: 'Secure', color: '#2F7D6D', items: [
    "I find it relatively easy to get emotionally close to others.",
    "I am comfortable depending on people I trust, and having them depend on me.",
    "I don't spend much time worrying about being abandoned or about someone getting \"too close.\"",
    "I feel confident that the people who matter to me will be there when I need them.",
    "I can express my needs and feelings fairly openly in close relationships.",
    "I generally trust that people who care about me don't intend to hurt me.",
    "I'm comfortable both being alone and being close to someone.",
    "Disagreements in a relationship don't make me fear the relationship is ending."] },
  { key: 'B', style: 'Anxious / Preoccupied', color: '#B7741B', items: [
    "I often worry that others don't truly love me or won't stay.",
    "I need frequent reassurance that I am loved or valued.",
    "I frequently worry that people close to me will leave or lose interest.",
    "I sometimes want to be extremely close to someone, which can feel overwhelming to them.",
    "I get anxious or upset when someone close to me spends time away from me.",
    "I spend a lot of mental energy worrying about my relationships.",
    "My mood is strongly affected by how a relationship seems to be going.",
    "I notice myself acting \"needy\" or seeking constant contact, even when I don't want to."] },
  { key: 'C', style: 'Avoidant / Dismissive', color: '#46679A', items: [
    "I prefer not to depend on others, or have others depend on me.",
    "I feel uncomfortable when someone wants a lot of emotional closeness.",
    "I find it hard to trust others completely, even people close to me.",
    "I place a high value on independence and self-sufficiency over closeness.",
    "I tend to keep my feelings to myself rather than share them with others.",
    "I feel uneasy when a partner or friend wants more closeness than I do.",
    "It's important to me that I don't \"need\" anyone.",
    "I tend to withdraw or create distance when a relationship starts to feel too intense."] },
  { key: 'D', style: 'Disorganized / Fearful-Avoidant', color: '#8C4A7E', items: [
    "I want closeness, but I also find it hard to fully trust the people I'm close to.",
    "I sometimes push people away even when part of me wants them near.",
    "My feelings toward someone I'm close to can swing quickly between wanting them near and wanting distance.",
    "I find relationships confusing. I want connection but also fear getting hurt.",
    "I'm often unsure what I actually want from a relationship.",
    "Past experiences make me cautious about opening up, even when I'd like to.",
    "I can feel a strong pull toward someone and an urge to keep them at arm's length at the same time.",
    "I've been told, or sense, that I send mixed signals in close relationships."] }
];

const PROFILES = {
  A: { desc: 'Generally comfortable with intimacy and independence. Trusts others, communicates needs directly, recovers well from conflict.',
       focus: 'Build on existing strengths; may still benefit from deepening self-awareness or navigating a specific relational challenge.' },
  B: { desc: "Craves closeness and reassurance, often fears abandonment, may over-monitor a relationship's status.",
       focus: 'Building internal security and self-soothing skills, tolerating uncertainty, distinguishing anxiety-driven thoughts from present reality.' },
  C: { desc: 'Values independence, may minimize the importance of close relationships, uncomfortable with vulnerability.',
       focus: 'Building tolerance for closeness and interdependence, practicing sharing feelings and needs, recognizing withdrawal patterns.' },
  D: { desc: 'Wants closeness but also fears it, often linked to past relational hurt. May oscillate between pursuing and withdrawing.',
       focus: 'Building safety and predictability, slowing down reactive patterns, working with self-compassion around the push-pull dynamic.' }
};

// Each option: [text, style key it echoes ('' = none)]
const REFLECT = [
  { id: 'R1', prompt: 'Depending on people usually leads to...', opts: [
    ['Feeling supported and closer to them', 'A'], ['Worrying about whether they will still be there', 'B'],
    ['Losing my independence or feeling trapped', 'C'], ['Getting hurt or let down in the end', 'D'],
    ['It depends a lot on the person', 'A']] },
  { id: 'R2', prompt: 'When someone gets too close to me, I usually...', opts: [
    ['Welcome it and enjoy the connection', 'A'], ['Want even more closeness and reassurance', 'B'],
    ['Pull back or need more space', 'C'], ['Get busy with work or other things', 'C'],
    ['Feel drawn in, then want to push them away', 'D']] },
  { id: 'R3', prompt: 'The hardest thing for me in relationships is...', opts: [
    ['Working through conflict or difficult conversations', 'A'], ['Not knowing where I stand', 'B'],
    ['Letting someone in and being vulnerable', 'C'], ["Trusting that I won't get hurt", 'D'],
    ['Asking for what I need', 'B']] },
  { id: 'R4', prompt: 'People usually see me as...', opts: [
    ['Warm and dependable', 'A'], ['Caring, but sometimes intense or clingy', 'B'],
    ['Independent, private or hard to read', 'C'], ['Strong, the one who has it all together', 'C'],
    ['Hot and cold, or hard to figure out', 'D']] },
  { id: 'R5', prompt: 'Very few people know that I...', opts: [
    ['Worry a lot about being left or replaced', 'B'], ['Find closeness uncomfortable', 'C'],
    ['Want closeness but am scared of it', 'D'], ['Carry past experiences that still shape how I trust', 'D'],
    ['Am more sensitive than I let on', '']] },
  { id: 'R6', prompt: 'When I feel emotionally unsafe, I tend to...', opts: [
    ['Name it and talk it through', 'A'], ['Seek reassurance or reach out repeatedly', 'B'],
    ['Shut down or withdraw', 'C'], ['Distract myself with work, my phone or keeping busy', 'C'],
    ['Swing between reaching out and pulling away', 'D']] }
];

const INTRO = 'This questionnaire helps you build an understanding of your relational patterns: how you tend to think, feel and behave in close relationships (romantic partners, close friends, family). It draws on four attachment styles used widely in coaching and therapeutic contexts: Secure, Anxious (Preoccupied), Avoidant (Dismissive) and Disorganized (Fearful-Avoidant).\n\n' +
  'This is a self-reflection and conversation-starting tool, not a clinical or diagnostic instrument. Answer honestly and intuitively, based on how you generally feel across close relationships (not just one relationship), rather than how you think you "should" feel.\n\n' +
  'Rate each statement from 1 to 5: 1 = Strongly Disagree, 2 = Disagree, 3 = Neutral / Sometimes true, 4 = Agree, 5 = Strongly Agree.\n\n' +
  'There are no right or wrong answers. Allow about 15 to 20 minutes.\n\nDesigned by Sylvia Lyne Njoki';

const CLOSING = 'Thank you for taking the time to complete this questionnaire. Some of these questions may have invited you to revisit experiences or emotions that aren\'t always easy to reflect on. Your willingness to do so speaks to your courage and your commitment to understanding yourself more deeply.\n\n' +
  'Please remember that this questionnaire is not a measure of your worth, nor is it intended to place you in a box. It is simply a starting point, a way for us to better understand the patterns you\'ve developed, many of which were shaped by your experiences and served a purpose at some point in your life.\n\n' +
  'Every pattern has a story, and every story deserves compassion. My hope is that, through our work together, you\'ll gain greater clarity, self-awareness, and practical tools to help you move toward the person you truly are.';

// ---------- Setup: builds the Form, Sheet, Dashboard and trigger ----------
function setup() {
  const form = FormApp.create(FORM_TITLE);
  form.setDescription(INTRO)
      .setProgressBar(true)
      .setConfirmationMessage(CLOSING + '\n\nIf you gave an email address, your results summary is on its way.')
      .setAllowResponseEdits(false)
      .setShowLinkToRespondAgain(false);

  const map = {};   // itemId -> code (A1..D8, R1..R6, NAME, EMAIL)

  const nameItem = form.addTextItem().setTitle('Your name or initials').setRequired(false);
  map[nameItem.getId()] = 'NAME';
  const emailItem = form.addTextItem()
      .setTitle('Email address to receive your results (optional)')
      .setHelpText('Your scores and reflections will be sent here after you submit.')
      .setValidation(FormApp.createTextValidation().requireTextIsEmail()
      .setHelpText('Please enter a valid email address.').build());
  map[emailItem.getId()] = 'EMAIL';

  SECTIONS.forEach(function (sec) {
    form.addPageBreakItem().setTitle('Section ' + sec.key)
        .setHelpText('Rate each statement from 1 (Strongly Disagree) to 5 (Strongly Agree).');
    sec.items.forEach(function (text, i) {
      const it = form.addScaleItem().setTitle((i + 1) + '. ' + text)
          .setBounds(1, 5).setLabels('Strongly Disagree', 'Strongly Agree').setRequired(true);
      map[it.getId()] = sec.key + (i + 1);
    });
  });

  form.addPageBreakItem().setTitle('Self-reflection')
      .setHelpText('These are powerful because there isn\'t a "correct" answer. Complete each sentence: tick every ending that fits, or choose "Other" to write your own.');
  REFLECT.forEach(function (r) {
    const it = form.addCheckboxItem().setTitle('"' + r.prompt + '"')
        .setChoiceValues(r.opts.map(function (o) { return o[0]; }))
        .showOtherOption(true).setRequired(false);
    map[it.getId()] = r.id;
  });

  // Linked spreadsheet
  const ss = SpreadsheetApp.create(FORM_TITLE + ' (Responses and Scores)');
  buildScoreSheets_(ss);   // build Scores/Dashboard first so the raw responses tab is added after them
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  const props = PropertiesService.getScriptProperties();
  props.setProperties({ FORM_ID: form.getId(), SHEET_ID: ss.getId(), ITEM_MAP: JSON.stringify(map) });

  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'onSubmit') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('onSubmit').forForm(form).onFormSubmit().create();

  Logger.log('Share this link with respondents: ' + form.getPublishedUrl());
  Logger.log('Edit the form: ' + form.getEditUrl());
  Logger.log('Scores and dashboard: ' + ss.getUrl());
}

function buildScoreSheets_(ss) {
  // Scores tab
  let sh = ss.getSheets()[0];
  sh.setName('Scores');
  const head = ['Submitted', 'Name', 'Email', 'A Secure', 'B Anxious', 'C Avoidant', 'D Disorganized',
    'Dominant style', 'Also elevated', 'Notes', 'Reflection lean (A/B/C/D)']
    .concat(REFLECT.map(function (r) { return r.prompt; }))
    .concat(SECTIONS.map(function (s) { return 'Items ' + s.key; }));
  sh.getRange(1, 1, 1, head.length).setValues([head]).setFontWeight('bold').setBackground('#E6EEEB').setWrap(true);
  sh.setFrozenRows(1);
  sh.setColumnWidths(1, head.length, 150);
  SECTIONS.forEach(function (s, i) { sh.getRange(1, 4 + i).setFontColor(s.color); });
  // colour scale on totals
  const rule = SpreadsheetApp.newConditionalFormatRule().setGradientMinpointWithValue('#FFFFFF', SpreadsheetApp.InterpolationType.NUMBER, '8')
      .setGradientMaxpointWithValue('#7FB3A8', SpreadsheetApp.InterpolationType.NUMBER, '40')
      .setRanges([sh.getRange('D2:G1000')]).build();
  sh.setConditionalFormatRules([rule]);

  // Dashboard tab
  const db = ss.insertSheet('Dashboard');
  db.getRange('A1').setValue('Behavioural Blueprint: group dashboard').setFontSize(14).setFontWeight('bold');
  db.getRange('A2').setFormula('="Responses scored: "&COUNTA(Scores!A2:A)');
  db.getRange('A4:D4').setValues([['Section', 'Average total (8 to 40)', 'Dominant for (people)', 'High (28+) for (people)']]).setFontWeight('bold').setBackground('#E6EEEB');
  const cols = { A: 'D', B: 'E', C: 'F', D: 'G' };
  const keyword = { A: 'Secure', B: 'Anxious', C: 'Avoidant', D: 'Disorganized' };
  SECTIONS.forEach(function (s, i) {
    const r = 5 + i, c = cols[s.key];
    db.getRange(r, 1).setValue(s.key + ' ' + s.style);
    db.getRange(r, 2).setFormula('=IFERROR(ROUND(AVERAGE(Scores!' + c + '2:' + c + '),1),0)');
    db.getRange(r, 3).setFormula('=COUNTIF(Scores!H2:H,"*' + keyword[s.key] + '*")');
    db.getRange(r, 4).setFormula('=COUNTIF(Scores!' + c + '2:' + c + ',">=28")');
  });
  db.getRange('A10').setValue('Band guide: Low 8 to 16, Moderate 17 to 27, High 28 to 40 (reading aid; the original tool scores on the highest total only). Tied highest totals count toward each tied style.').setFontColor('#5D6B68');
  db.setColumnWidth(1, 240); db.setColumnWidths(2, 3, 170);

  db.insertChart(db.newChart().asBarChart().addRange(db.getRange('A4:B8'))
      .setOption('title', 'Average section totals').setOption('legend', { position: 'none' })
      .setOption('hAxis', { minValue: 8, maxValue: 40 }).setOption('colors', ['#2B6B63'])
      .setPosition(12, 1, 0, 0).build());
  db.insertChart(db.newChart().asColumnChart().addRange(db.getRange('A4:A8')).addRange(db.getRange('C4:C8'))
      .setOption('title', 'Dominant style count').setOption('legend', { position: 'none' })
      .setOption('colors', ['#8C4A7E']).setPosition(12, 5, 0, 0).build());
}

// ---------- Scoring ----------
function score_(totals) {
  const t = SECTIONS.map(function (s) { return { key: s.key, style: s.style, color: s.color, total: totals[s.key] }; });
  const max = Math.max.apply(null, t.map(function (x) { return x.total; }));
  const dom = t.filter(function (x) { return x.total === max; });
  const band = function (v) { return v >= 28 ? 'High' : v >= 17 ? 'Moderate' : 'Low'; };
  const elevated = t.filter(function (x) { return dom.indexOf(x) < 0 && (x.total >= 28 || max - x.total <= 3); });
  const sorted = t.slice().sort(function (a, b) { return b.total - a.total; });
  const T = totals, notes = [];
  if (dom.length > 1) notes.push('Your highest totals are tied (' + dom.map(function (d) { return d.style; }).join(' and ') + '). Read both profiles together.');
  if (T.B >= 28 && T.C >= 28 && !dom.some(function (d) { return d.key === 'D'; }))
    notes.push('Anxious (B) and Avoidant (C) are both high. Wanting closeness while guarding against it is the push-pull pattern described under Disorganized / Fearful-Avoidant, so that profile is worth reading too.');
  if (dom.some(function (d) { return d.key === 'A'; }) && t.some(function (x) { return x.key !== 'A' && x.total >= 28; }))
    notes.push('Secure is highest, but another dimension is also high. This often shows up as a secure base with specific situations or relationships that bring out a different pattern.');
  if (max < 17) notes.push('All four totals are low, so no dimension stands out strongly. The reflections and a conversation may say more than the numbers.');
  const gap = sorted[0].total - sorted[1].total;
  if (dom.length === 1 && gap > 0 && gap <= 3) notes.push('Your top two dimensions are only ' + gap + ' point' + (gap > 1 ? 's' : '') + ' apart. Treat ' + sorted[1].style + ' as close to equally present.');
  return { t: t, dom: dom, elevated: elevated, notes: notes, band: band };
}

function onSubmit(e) {
  processResponse_(e.response, true);
}

function processResponse_(resp, sendMail) {
  const props = PropertiesService.getScriptProperties();
  const map = JSON.parse(props.getProperty('ITEM_MAP'));
  const ss = SpreadsheetApp.openById(props.getProperty('SHEET_ID'));

  const items = { A: [], B: [], C: [], D: [] }, refl = {};
  let name = '', email = '';
  resp.getItemResponses().forEach(function (ir) {
    const code = map[ir.getItem().getId()];
    if (!code) return;
    const v = ir.getResponse();
    if (code === 'NAME') name = String(v || '').trim();
    else if (code === 'EMAIL') email = String(v || '').trim();
    else if (code.charAt(0) === 'R') refl[code] = v || [];
    else items[code.charAt(0)][Number(code.substring(1)) - 1] = Number(v);
  });

  const totals = {};
  SECTIONS.forEach(function (s) { totals[s.key] = items[s.key].reduce(function (a, b) { return a + (b || 0); }, 0); });
  const r = score_(totals);

  // reflections
  const lean = { A: 0, B: 0, C: 0, D: 0 };
  const reflRows = REFLECT.map(function (q) {
    const picked = refl[q.id] || [];
    return picked.map(function (p) {
      const hit = q.opts.filter(function (o) { return o[0] === p; })[0];
      if (hit && hit[1]) lean[hit[1]]++;
      return hit ? { text: p, key: hit[1] } : { text: 'Other: ' + p, key: '' };
    });
  });

  // write Scores row
  const row = [resp.getTimestamp(), name, email, totals.A, totals.B, totals.C, totals.D,
    r.dom.map(function (d) { return d.style; }).join(' & '),
    r.elevated.map(function (d) { return d.style; }).join(', '),
    r.notes.join(' '),
    [lean.A, lean.B, lean.C, lean.D].join(' / ')]
    .concat(reflRows.map(function (arr) { return arr.map(function (x) { return x.text; }).join('; '); }))
    .concat(SECTIONS.map(function (s) { return items[s.key].join(','); }));
  ss.getSheetByName('Scores').appendRow(row);

  // email
  const html = resultsHtml_(name, totals, r, reflRows, lean);
  const subject = 'Your Behavioural Blueprint results' + (name ? ': ' + name : '');
  if (!sendMail) return;
  if (email) MailApp.sendEmail({ to: email, subject: subject, htmlBody: html, name: 'Behavioural Blueprint Assessment' });
  if (COACH_EMAIL) MailApp.sendEmail({ to: COACH_EMAIL, subject: '[Copy] ' + subject + (email ? ' (' + email + ')' : ''), htmlBody: html });
}

function resultsHtml_(name, totals, r, reflRows, lean) {
  const esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  const max = Math.max(totals.A, totals.B, totals.C, totals.D);
  let h = '<div style="font-family:Arial,sans-serif;color:#1D2927;max-width:620px;line-height:1.5">';
  h += '<p style="font-size:12px;letter-spacing:1px;color:#5D6B68;text-transform:uppercase;margin:0">Behavioural Blueprint Assessment</p>';
  h += '<h2 style="margin:4px 0 12px">' + (name ? esc(name) + ', your results' : 'Your results') + '</h2>';
  h += '<p style="margin:0;color:#5D6B68">' + (r.dom.length > 1 ? 'Co-dominant tendencies' : 'Dominant tendency') + ' (highest section total)</p>';
  h += '<p style="font-size:22px;margin:2px 0 14px;font-family:Georgia,serif">' +
       r.dom.map(function (d) { return '<span style="color:' + d.color + '">' + d.style + '</span>'; }).join(' &amp; ') + '</p>';

  // bar chart
  h += '<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse">';
  r.t.forEach(function (x) {
    const pct = Math.round((x.total - 8) / 32 * 100);
    h += '<tr><td style="width:150px;padding:5px 8px 5px 0;font-size:13px;' + (x.total === max ? 'font-weight:bold' : '') + '">' + x.key + ' ' + x.style.split(' /')[0] + '</td>' +
         '<td style="padding:5px 0"><div style="background:#E6EEEB;border-radius:3px;height:18px;width:100%"><div style="background:' + x.color + ';height:18px;border-radius:3px;width:' + Math.max(pct, 1) + '%"></div></div></td>' +
         '<td style="width:90px;padding-left:8px;font-size:13px"><b>' + x.total + '</b>/40 ' + r.band(x.total) + '</td></tr>';
  });
  h += '</table><p style="font-size:11px;color:#5D6B68">Scale 8 to 40 per section. Bands: Low 8 to 16, Moderate 17 to 27, High 28 to 40.</p>';

  if (r.elevated.length) h += '<p>Also elevated: <b>' + r.elevated.map(function (e) { return e.style + ' (' + e.total + ')'; }).join(', ') + '</b>. It is common and expected for more than one dimension to be raised.</p>';
  r.notes.forEach(function (n) { h += '<p style="font-size:14px">' + esc(n) + '</p>'; });

  h += '<h3 style="margin-top:22px">All four possible outcomes</h3>';
  SECTIONS.forEach(function (s) {
    const hit = r.dom.some(function (d) { return d.key === s.key; });
    h += '<div style="border:' + (hit ? '2px solid ' + s.color : '1px solid #D9E0DD') + ';border-radius:8px;padding:10px 12px;margin:8px 0">' +
         '<b style="color:' + s.color + '">Section ' + s.key + ': ' + s.style + ' (' + totals[s.key] + '/40)' + (hit ? ', your highest' : '') + '</b>' +
         '<p style="margin:4px 0;font-size:14px">' + PROFILES[s.key].desc + '</p>' +
         '<p style="margin:4px 0;font-size:14px"><b>Coaching focus:</b> ' + PROFILES[s.key].focus + '</p></div>';
  });

  h += '<h3 style="margin-top:22px">Your reflections</h3>';
  const leanTxt = SECTIONS.filter(function (s) { return lean[s.key]; }).map(function (s) { return lean[s.key] + ' ' + s.style.split(' /')[0]; }).join(', ');
  if (leanTxt) h += '<p style="font-size:13px;color:#5D6B68">Endings you chose echo these themes: ' + leanTxt + '. This is a prompt for conversation, not a score.</p>';
  REFLECT.forEach(function (q, i) {
    h += '<p style="margin:10px 0 2px;font-style:italic;color:#5D6B68">"' + esc(q.prompt) + '"</p>';
    h += '<p style="margin:0">' + (reflRows[i].length ? reflRows[i].map(function (x) { return esc(x.text); }).join('; ') : '<span style="color:#9AA9A5">Not answered</span>') + '</p>';
  });

  h += '<hr style="border:none;border-top:1px solid #D9E0DD;margin:22px 0">';
  h += '<p style="font-family:Georgia,serif;font-size:14px;white-space:pre-line">' + esc(CLOSING) + '</p>';
  h += '<p style="font-size:11px;color:#5D6B68">This is a self-reflection and conversation-starting tool, not a clinical or diagnostic instrument.</p></div>';
  return h;
}

// ---------- Optional: re-score all existing responses into the Scores tab ----------
function rescoreAll() {
  const props = PropertiesService.getScriptProperties();
  const form = FormApp.openById(props.getProperty('FORM_ID'));
  const ss = SpreadsheetApp.openById(props.getProperty('SHEET_ID'));
  const sh = ss.getSheetByName('Scores');
  if (sh.getLastRow() > 1) sh.getRange(2, 1, sh.getLastRow() - 1, sh.getLastColumn()).clearContent();
  form.getResponses().forEach(function (resp) { processResponse_(resp, false); });
}
