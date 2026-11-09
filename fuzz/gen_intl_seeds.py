#!/usr/bin/env python3
"""Deterministic structured seed generation for the QuickJS fuzz targets.

Emits small JS files that drive the Intl.* and Temporal.* builtins (plus a few
libunicode entry points) so fuzz_eval / fuzz_compile start deep inside the
locale parsers, formatters and calendar code instead of having to discover the
API surface through the JS grammar.  Run from the OSS-Fuzz build:

    python3 fuzz/gen_intl_seeds.py --out-dir <dir>

The output is deterministic: same script version, same seeds.  Generated files
land in the fuzz_eval/fuzz_compile seed corpus zips next to the quickjs-corpus
samples.  A seed may legitimately throw (unsupported option combinations are
part of the surface); each file guards the call so an exception never hides
later statements.
"""

import argparse
import os

def try_wrap(body):
    """Wrap statements so an expected exception does not hide the rest."""
    stmts = [s.strip() for s in body.split(';') if s.strip()]
    lines = ['try {']
    lines += ['  ' + s for s in stmts]
    lines.append('} catch (e) {}')
    return '\n'.join(lines)

LOCALES = [
    'en', 'en-US', 'de-DE-u-co-phonebk', 'ar-EG-u-nu-arab', 'zh-Hant-TW',
    'ja-JP-u-ca-japanese', 'und', 'th-TH-u-nu-thai-x-private', 'sr-Cyrl-RS',
    'es-419', 'pt-PT', 'az-Latn-AZ', 'lt-LT', 'pl-PL', 'ga-IE', 'cy-GB',
    'sl-SI', 'lv-LV', 'he-IL-u-ca-hebrew', 'fa-IR-u-ca-persian',
    'en-u-nu-fullwide', 'de-u-kn-true-kf-upper', 'und-u-va-posix',
    'xx-YY', 'xx-YY-ZZZZ-AAA', 'en--US', 'e', '123', 'en-u-', 'en-u-nu-',
    'en-u-nu-arab-u-ca-gregory', 'e-u-', 'en-Latn-US-macos', 'EN-us',
    'root', 'en-a-b', 'en-x-private-use-tag', 'und-ES-u-rg-espct',
]

CAL = ['iso8601', 'gregory', 'islamic', 'islamic-umalqura', 'islamic-civil',
       'chinese', 'coptic', 'ethioaa', 'hebrew', 'japanese', 'persian',
       'roc', 'indian', 'buddhist', 'saudi', 'islamic-rgsa']

TZ = ['UTC', 'America/New_York', 'Etc/GMT+12', 'Etc/GMT-14', 'Australia/Lord_Howe',
      'Pacific/Apia', 'Asia/Kathmandu', 'Europe/Dublin', '+05:30', '-08:00',
      '+1345', 'Z', 'NoSuch/Zone', 'AMERICA/New_YORK']

seeds = {}

def add(name, body):
    seeds[name] = try_wrap(body)

# ---- Intl.DateTimeFormat: time zone / calendar / style matrix ---------
dt_opts = [
    {('dateStyle', 'full'), ('timeStyle', 'full')},
    {('dateStyle', 'long')}, {('timeStyle', 'medium')},
    {('hourCycle', 'h11')}, {('hourCycle', 'h24')},
    {('hour12', 'true'), ('timeZoneName', 'shortOffset')},
    {('timeZoneName', 'longGeneric')},
    {('month', 'long'), ('era', 'short'), ('weekday', 'long')},
    {('fractionalSecondDigits', '9')},
    {('dayPeriod', 'short'), ('hour', 'numeric')},
    {('year', '2-digit'), ('month', 'numeric'), ('day', '2-digit')},
]
for i, tz in enumerate(TZ):
    o = ', '.join('%s: %r' % kv for kv in sorted(dt_opts[i % len(dt_opts)]))
    add('dtfmt-%02d' % i,
        "var d = new Intl.DateTimeFormat(%r, {timeZone: %r, %s});"
        " d.format(new Date('2020-02-29T13:37:42Z')); d.formatToParts(new Date(0));"
        " d.resolvedOptions(); d.formatRange(new Date(0), new Date(1e12));"
        % (LOCALES[i % len(LOCALES)], tz, o))
extremes = ["new Date(-62135596800000)", "new Date(8.64e15)", "new Date(-8.64e15)",
            "new Date(1)", "new Date('275760-09-13T00:00:00Z')"]
for i, cal in enumerate(CAL):
    add('dtfmt-cal-%02d' % i,
        "var d = new Intl.DateTimeFormat('en-u-ca-%s', {dateStyle: 'full', timeStyle: 'long'});"
        " d.format(%s); d.formatToParts(%s); d.resolvedOptions().calendar;"
        % (cal, extremes[i % len(extremes)], extremes[i % len(extremes)]))

# ---- Intl.Collator ----------------------------------------------------
coll_opts = [
    {('sensitivity', 'variant')}, {('sensitivity', 'base')},
    {('sensitivity', 'accent'), ('caseFirst', 'upper')},
    {('ignorePunctuation', 'true')}, {('numeric', 'true')},
    {('collation', 'phonebk')}, {('collation', 'pinyin')},
    {('collation', 'stroke')}, {('collation', 'zhuyin')},
]
strs = ["['a', 'A', 'ä', 'Å', 'z']", "['1', '10', '2', '٠١', '²']",
        "['stoff', 'stop', 'estoff', 'ästoff']", "['①', '⑴', '一', 'い']",
        "['a\\u0301', 'á', 'b\\u200dñ', 'X\\ufb03']"]
for i, opts in enumerate(coll_opts):
    o = ', '.join('%s: %r' % kv for kv in sorted(opts))
    add('coll-%02d' % i,
        "var c = new Intl.Collator(%r, {%s}); var a = %s; a.sort(c.compare);"
        " c.compare('a', 'á'); c.resolvedOptions();" % (LOCALES[(i * 3) % len(LOCALES)], o, strs[i % len(strs)]))

# ---- Intl.PluralRules / RelativeTimeFormat / ListFormat --------------
for i, loc in enumerate(['ar', 'pl', 'ga', 'cy', 'sl', 'lv', 'en', 'ja', 'ro', 'fr']):
    add('plural-%02d' % i,
        "var p = new Intl.PluralRules(%r); [0, 0.5, 1, 1.5, 2, 2.5, 3, 5, 11, 21, 100, 1000, 1e6]"
        ".forEach(function (n) { p.select(n); });"
        " new Intl.PluralRules(%r, {type: 'ordinal'}).select(3);"
        " new Intl.PluralRules(%r, {type: 'range'}).selectRange(1, 2);"
        % (loc, loc, loc))
    add('rtf-%02d' % i,
        "var r = new Intl.RelativeTimeFormat(%r, {numeric: 'auto'});"
        " r.format(-3, 'quarter'); r.format(1, 'day'); r.format(2.5, 'hour');"
        " r.formatToParts(-1, 'week'); r.format(42, 'second');"
        " new Intl.RelativeTimeFormat(%r, {style: 'narrow', numeric: 'always'}).format(-2, 'year');"
        % (loc, loc))
    add('listfmt-%02d' % i,
        "var l = new Intl.ListFormat(%r, {type: 'conjunction'});"
        " l.format(['a', 'b', 'c']); l.formatToParts(['x', 'y']);"
        " new Intl.ListFormat(%r, {type: 'disjunction', style: 'narrow'}).format(['1', '2', '3', '4']);"
        " new Intl.ListFormat(%r, {type: 'unit'}).format(['5 lb', '12 oz']);"
        % (loc, loc, loc))

# ---- Intl.DisplayNames ------------------------------------------------
for i, (t, code) in enumerate([('language', 'zh-Hant-TW'), ('language', 'und-Latn'),
                               ('region', '419'), ('region', 'ZZ'), ('script', 'Cyrl'),
                               ('script', 'Qaai'), ('currency', 'USD'), ('currency', 'XXX'),
                               ('dateField', 'sat'), ('dateField', 'satNext')]):
    add('displaynames-%02d' % i,
        "var d = new Intl.DisplayNames(%r, {type: %r}); d.of(%r); d.of('bogus');"
        % (LOCALES[i % len(LOCALES)], t, code))

# ---- Intl.Segmenter ---------------------------------------------------
texts = ["'a\\u0301bc'", "'\\ud83d\\ude00\\ud83e\\uddd1\\u200d\\ud83e\\uddb0hi'",
         "'The quick brown fox. Jumps over? Yes!'", "'เพ็ชรไทย'",
         "'中文，繁體字。日本語のテキスト。'", "'don\\u2019t stop-me now\\u2026'",
         "'\\ud800\\ud800\\ud800'", "'x\\u0301\\u0302\\u0303y'"]
for i, g in enumerate(['grapheme', 'word', 'sentence']):
    for j, t in enumerate(texts):
        add('seg-%s-%d' % (g, j),
            "var s = new Intl.Segmenter(%r, {granularity: %r}); var it = s.segment(%s)[Symbol.iterator]();"
            " var r; while (!(r = it.next()).done) { r.value.segment; r.value.index; r.value.isWordLike; }"
            " s.resolvedOptions();" % (LOCALES[j % len(LOCALES)], g, t))

# ---- Intl.DurationFormat ---------------------------------------------
dur_args = [
    "{years: 1, months: 2, weeks: 3, days: 4, hours: 5, minutes: 6, seconds: 7,"
    " milliseconds: 8, microseconds: 9, nanoseconds: 10}",
    "{hours: 275760}", "{days: -1}", "{seconds: 1e15}",
    "{months: 12, days: 40, minutes: 90}",
]
for i, a in enumerate(dur_args):
    add('durfmt-%02d' % i,
        "var f = new Intl.DurationFormat(%r, {style: 'digital'}); f.format(%s);"
        " f.resolvedOptions();"
        " new Intl.DurationFormat(%r, {years: 'long', hours: 'narrow', milliseconds: 'numeric',"
        " fractionalDigits: 9}).format(%s);" % (LOCALES[i % len(LOCALES)], a, LOCALES[(i + 1) % len(LOCALES)], a))
for i, tag in enumerate(LOCALES):
    add('locale-%02d' % i,
        "var l = new Intl.Locale(%r); l.maximize(); l.minimize(); l.toString();"
        " l.language; l.script; l.region; l.calendars; l.collations;"
        " l.hourCycles; l.numberingSystems; l.nu; l.ca; l.kn; l.kf;" % tag)

# ---- Intl.NumberFormat: option matrix ---------------------------------
nf_opts = [
    {('style', 'currency'), ('currency', 'USD'), ('currencyDisplay', 'narrowSymbol')},
    {('style', 'currency'), ('currency', 'XXX'), ('currencyDisplay', 'name')},
    {('style', 'unit'), ('unit', 'meter'), ('unitDisplay', 'long')},
    {('style', 'unit'), ('unit', 'bit'), ('unitDisplay', 'narrow')},
    {('style', 'percent')},
    {('notation', 'scientific'), ('minExponentDigits', '5')},
    {('notation', 'engineering'), ('compactDisplay', 'short')},
    {('notation', 'compact'), ('compactDisplay', 'long')},
    {('signDisplay', 'always')}, {('signDisplay', 'exceptZero')},
    {('signDisplay', 'negative')}, {('signDisplay', 'never')},
    {('minimumFractionDigits', '30'), ('maximumFractionDigits', '100')},
    {('minimumIntegerDigits', '21')},
    {('minimumSignificantDigits', '1'), ('maximumSignificantDigits', '21')},
    {('roundingMode', 'expand')}, {('roundingMode', 'floor')},
    {('roundingMode', 'halfEven'), ('roundingIncrement', '500')},
    {('trailingZeroDisplay', 'stripIfInteger')},
    {('useGrouping', 'min2')},
]
vals = ['1234.5678', '-0', '1e21', 'NaN', 'Infinity', '-1234.5678', '0.000001']
for i, opts in enumerate(nf_opts):
    o = ', '.join('%s: %r' % kv for kv in sorted(opts))
    v = vals[i % len(vals)]
    add('numfmt-%02d' % i,
        "var f = new Intl.NumberFormat(%r, {%s});"
        " f.format(%s); f.formatToParts(%s); f.resolvedOptions();"
        " f.formatRange(1.5, 2.5); f.formatRangeToParts(1, 2);" % (LOCALES[i % len(LOCALES)], o, v, v))

# ---- Temporal: ISO string parsing across all constructors -------------
iso_strings = [
    '2020-02-29', '-271821-04-20', '+275760-09-13', '2020-02-30',
    '1970-01-01T00:00:00Z', '1970-01-01T00:00:00.123456789Z',
    '2020-01-01T24:00:00', '2020-01-01T00:60:00', '2020-01-01T00:00:60.9',
    '+009999-01-01', '-000001-01-01', '2020-01-01T00:00:00+24:00',
    '2020-01-01T00:00:00[UTC]', '2020-01-01T00:00:00-08:00[America/New_York]',
    'P1Y2M3W4DT5H6M7.5S', '-P1Y2M3W4DT5H6M7.5S', 'PT0.000000001S',
    'PT8640000000000000S', 'P0D',
]
ctors = ['Temporal.PlainDate.from', 'Temporal.PlainTime.from',
         'Temporal.PlainDateTime.from', 'Temporal.PlainYearMonth.from',
         'Temporal.PlainMonthDay.from', 'Temporal.Instant.from',
         'Temporal.Duration.from', 'Temporal.PlainTime.from']
for i, s in enumerate(iso_strings):
    ctor = ctors[i % len(ctors)]
    add('temporal-iso-%02d' % i,
        "%s(%r); %s(%r, {overflow: 'constrain'});" % (ctor, s, ctor, s))

# ---- Temporal: arithmetic, rounding, calendar math --------------------
temporal_snippets = [
    "var i = Temporal.Instant.from('2020-01-01T00:00:00Z'); i.add({hours: 9007199254740991});"
    " i.subtract({nanoseconds: 1e18}); i.round({largestUnit: 'year', smallestUnit: 'nanosecond'});"
    " i.until(Temporal.Instant.from('2021-01-01T00:00:00Z'), {largestUnit: 'day'});"
    " i.toString({fractionalSecondDigits: 'auto', timeZone: 'UTC'}); i.epochSeconds; i.epochMicroseconds;",
    "var d = Temporal.PlainDate.from('2020-02-29'); d.add({years: 1, months: 12, days: 400});"
    " d.subtract({weeks: 53}); d.until('2021-02-28', {largestUnit: 'year'});"
    " d.inLeapYear; d.daysInMonth; d.daysInYear; d.weekOfYear; d.dayOfWeek; d.eraYear;"
    " d.toString({calendarName: 'always'}); d.with({month: 13});",
    "var dt = Temporal.PlainDateTime.from('2020-06-15T12:34:56.789123456');"
    " dt.round({smallestUnit: 'hour', roundingMode: 'ceil'});"
    " dt.round({smallestUnit: 'minute', roundingIncrement: 17});"
    " dt.withCalendar('islamic-umalqura').toString(); dt.withTimeZone('UTC').toString();",
    "var ym = Temporal.PlainYearMonth.from({year: 2400, month: 2, calendar: 'hebrew'});"
    " ym.daysInMonth; ym.add({years: 10000}); ym.toString();",
    "var md = Temporal.PlainMonthDay.from({monthCode: 'M02', day: 29});"
    " md.toPlainDate({year: 2021}).toString(); md.toString();",
    "var z = Temporal.PlainDateTime.from('2021-03-14T01:30:00').toZonedDateTime('America/New_York');"
    " z.offsetNanoseconds; z.startOfDay(); z.toInstant(); z.hoursInDay;"
    " Temporal.PlainDateTime.from('2021-11-07T01:30:00').toZonedDateTime('America/New_York').offset;",
    "var dur = Temporal.Duration.from({hours: 1, minutes: 30});"
    " dur.round({relativeTo: '2020-01-01', largestUnit: 'year', smallestUnit: 'minute'});"
    " dur.total({unit: 'minutes'}); dur.negated().toString();"
    " Temporal.Duration.from({hours: 2}).add(dur).toString();",
    "var c = Temporal.Calendar.from('chinese');"
    " c.dateFromFields({year: 2020, monthCode: 'M01', day: 1}, {overflow: 'reject'});"
    " c.dateAdd('2020-01-01', {months: 13}); c.dateUntil('2020-01-01', '2021-01-01');"
    " c.era('2020-01-01'); c.dayOfYear('2020-06-01'); c.isLeapYear(2400);",
    "Temporal.Now.instant(); Temporal.Now.timeZoneId();"
    " Temporal.Now.plainDateISO('Asia/Tokyo').toString();"
    " Temporal.Now.zonedDateTimeISO('UTC').offsetNanoseconds;",
    "Temporal.Instant.fromEpochNanoseconds(8640000000000000000000n - 1n);"
    " Temporal.Instant.fromEpochNanoseconds(-8640000000000000000000n);"
    " Temporal.Instant.fromEpochMilliseconds(8.64e15);",
    "Temporal.PlainDate.compare('2020-01-01', '2021-01-01');"
    " Temporal.Duration.from('P1D').compare(Temporal.Duration.from('PT24H'));"
    " Temporal.ZonedDateTime.from('2020-01-01T00:00+01:00[Europe/Paris]').dayOfWeek;",
]
for i, snip in enumerate(temporal_snippets):
    add('temporal-ops-%02d' % i, snip)

# ---- libunicode: case mapping and normalisation -----------------------
uni_texts = [
    "'\\u0130'", "'i'", "'\\u0049\\u0307'", "'\\u0345'", "'\\ufb03'",
    "'\\ud83d\\ude00\\ud83c\\ddfa\\ud83c\\uddf8'", "'\\u00df'",
    "'\\u0301\\u0302\\u0303'", "'\\u1100\\u1161\\u11a8'", "'\\u00e5'",
]
for i, t in enumerate(uni_texts):
    add('unicode-%02d' % i,
        "(%s).normalize('NFC'); (%s).normalize('NFD'); (%s).normalize('NFKC');"
        " (%s).normalize('NFKD');" % (t, t, t, t))
for i, loc in enumerate(['lt-LT', 'az', 'tr', 'el', 'de-CH-1901', 'fi', 'und']):
    add('unicode-locale-%02d' % i,
        "'\\u0049\\u0307i\\u0130'.toLocaleUpperCase(%r); 'I\\u0307'.toLocaleLowerCase(%r);"
        " '\\u00c5'.toLocaleUpperCase(%r);" % (loc, loc, loc))

# ---- safe quickjs-libc surface ---------------------------------------
# Deliberately NO timer seeds: the fuzz harnesses finish every iteration in
# js_std_loop(), which polls forever (10s poll cycles) as long as any timer
# stays armed — mutated delays (e.g. 1e9 ms) or a mutated-away clearTimeout
# turn armed timers into libFuzzer timeouts. os.exec/os.Worker stay excluded
# as before; the os-module import itself (fuzz_common.c) keeps that surface
# reachable for the fuzzer's own exploration.


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    for name in sorted(seeds):
        path = os.path.join(args.out_dir, 'gen-%s.js' % name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('// generated by fuzz/gen_intl_seeds.py -- do not edit\n')
            f.write(seeds[name])
            f.write('\n')
    print('wrote %d seeds to %s' % (len(seeds), args.out_dir))

if __name__ == '__main__':
    main()

