"""
Tests of the collector against a real MongoDB: adding, deleting and updating
day files, and whether the documents of the days that use a file follow
(issue #4).

They need a MongoDB without authentication; set WFCAT_TEST_MONGO_HOST and
WFCAT_TEST_MONGO_PORT (default 127.0.0.1:27017). Without one they are
skipped. They work in a database of their own, wfcatalog_pytest, which is
dropped before and after every test. The collector runs as a subprocess, the
way an operator starts it, on a copy of the bundled archive.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from obspy import read

pymongo = pytest.importorskip("pymongo")

COLLECTOR_DIR = Path(__file__).resolve().parent.parent
HOST = os.environ.get("WFCAT_TEST_MONGO_HOST", "127.0.0.1")
PORT = int(os.environ.get("WFCAT_TEST_MONGO_PORT", "27017"))
DBNAME = "wfcatalog_pytest"
USER = PASSWORD = "wfcatalog"

# The options the archive was ingested with; --update and --delete must repeat them
ALL_OPTIONS = ("--hourly", "--csegs", "--flags")


def mongo_available():
    try:
        pymongo.MongoClient(HOST, PORT, serverSelectionTimeoutMS=1500).admin.command("ping")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not mongo_available(), reason=f"no MongoDB at {HOST}:{PORT}")


@pytest.fixture
def db():
    client = pymongo.MongoClient(HOST, PORT)
    client.drop_database(DBNAME)
    database = client[DBNAME]
    # The collector always authenticates, against its own database. Users
    # survive drop_database, so the user may exist from an earlier run.
    try:
        database.command("createUser", USER, pwd=PASSWORD, roles=[{"role": "readWrite", "db": DBNAME}])
    except pymongo.errors.OperationFailure as error:
        if error.code != 51003:  # "User already exists"
            raise
    yield database
    client.drop_database(DBNAME)
    client.close()


@pytest.fixture
def archive(tmp_path):
    """A copy of the bundled archive that a test may change."""
    root = tmp_path / "archive"
    shutil.copytree(COLLECTOR_DIR / "archive", root)
    return root


def day_file(archive, day):
    return archive / "2017" / "NL" / "HGN" / "LHZ.D" / f"NL.HGN.02.LHZ.D.2017.{day:03d}"


def run_collector(archive, tmp_path, *arguments):
    env = {k: v for k, v in os.environ.items() if not k.startswith("WFCAT_")}
    env.update(
        {
            # Empty directory: no config.json, so the WFCAT_* variables apply.
            "WFCAT_CONF_DIR": str(tmp_path),
            "WFCAT_ARCHIVE_ROOT": str(archive),
            "WFCAT_MONGO_ENABLED": "true",
            "WFCAT_MONGO_HOST": HOST,
            "WFCAT_MONGO_PORT": str(PORT),
            "WFCAT_MONGO_DBNAME": DBNAME,
            "WFCAT_MONGO_USER": USER,
            "WFCAT_MONGO_PASS": PASSWORD,
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "src.WFCatalogCollector", *arguments],
        cwd=COLLECTOR_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout + result.stderr


def ingest(archive, tmp_path):
    return run_collector(archive, tmp_path, "--dir", str(archive), *ALL_OPTIONS)


def daily(db, day):
    return db.daily_streams.find_one({"fileId": f"NL.HGN.02.LHZ.D.2017.{day:03d}"})


def used_files(document):
    """The day numbers of the files a document was computed from."""
    return sorted(f["name"][-3:] for f in document["files"])


def hourly_count(db, document):
    return db.hourly_streams.count_documents({"streamId": document["_id"]})


def orphans(db):
    """Hourly granules and segments whose daily document is gone."""
    ids = [d["_id"] for d in db.daily_streams.find({}, {"_id": 1})]
    return db.hourly_streams.count_documents({"streamId": {"$nin": ids}}) + db.c_segments.count_documents(
        {"streamId": {"$nin": ids}}
    )


def test_ingest_records_which_files_each_day_uses(db, archive, tmp_path):
    ingest(archive, tmp_path)

    assert db.daily_streams.count_documents({}) == 3
    assert db.hourly_streams.count_documents({}) == 72
    assert used_files(daily(db, 21)) == ["021"]
    # The last record of a day file reaches into the next day
    assert used_files(daily(db, 22)) == ["021", "022"]
    assert used_files(daily(db, 23)) == ["022", "023"]


def test_delete_removes_the_day_and_refreshes_the_days_that_used_it(db, archive, tmp_path):
    ingest(archive, tmp_path)
    before = daily(db, 23)

    day_file(archive, 22).unlink()
    output = run_collector(archive, tmp_path, "--delete", "--file", str(day_file(archive, 22)), *ALL_OPTIONS)

    assert "Stage dependent file for update NL.HGN.02.LHZ.D.2017.023" in output
    assert daily(db, 22) is None
    assert db.daily_streams.count_documents({}) == 2
    after = daily(db, 23)
    assert after["_id"] != before["_id"], "day 023 was not recomputed"
    assert used_files(after) == ["023"]
    assert hourly_count(db, after) == 24
    assert orphans(db) == 0


def test_delete_without_the_ingest_options_warns_about_dropped_parts(db, archive, tmp_path):
    ingest(archive, tmp_path)

    day_file(archive, 22).unlink()
    output = run_collector(archive, tmp_path, "--delete", "--file", str(day_file(archive, 22)))

    # Day 023 is recomputed with the options of this run, so these parts are gone
    after = daily(db, 23)
    assert hourly_count(db, after) == 0
    assert "io_flags" not in after
    # and the log says so
    assert "NL.HGN.02.LHZ.D.2017.023 has hourly granules in the database that are dropped" in output
    assert "NL.HGN.02.LHZ.D.2017.023 has header flags in the database that are dropped" in output


def test_update_refreshes_the_changed_day_and_the_days_that_used_it(db, archive, tmp_path):
    ingest(archive, tmp_path)
    before = {day: daily(db, day)["_id"] for day in (21, 22, 23)}

    # Same data, longer records: a new checksum and a different record_length
    path = day_file(archive, 21)
    read(str(path)).write(str(path), format="MSEED", reclen=4096)
    output = run_collector(archive, tmp_path, "--update", "--dir", str(archive), *ALL_OPTIONS)

    assert "Discovered 2 file(s) with changed checksum in database" in output
    assert daily(db, 21)["_id"] != before[21]
    assert daily(db, 22)["_id"] != before[22], "day 022 uses file 021 and was not recomputed"
    assert daily(db, 23)["_id"] == before[23], "day 023 does not use file 021 but was recomputed"
    assert daily(db, 21)["rlen"] == [4096]
    assert sorted(daily(db, 22)["rlen"]) == [512, 4096]
    assert db.hourly_streams.count_documents({}) == 72
    assert orphans(db) == 0


def test_update_without_a_change_does_nothing(db, archive, tmp_path):
    ingest(archive, tmp_path)
    before = {day: daily(db, day)["_id"] for day in (21, 22, 23)}

    output = run_collector(archive, tmp_path, "--update", "--dir", str(archive), *ALL_OPTIONS)

    assert "Discovered 0 file(s) with changed checksum in database" in output
    assert {day: daily(db, day)["_id"] for day in (21, 22, 23)} == before


def late_file_setup(db, archive, tmp_path):
    """Ingest without day 022, then let the file arrive and ingest again."""
    saved = day_file(archive, 22).read_bytes()
    day_file(archive, 22).unlink()
    ingest(archive, tmp_path)
    assert used_files(daily(db, 23)) == ["023"]

    day_file(archive, 22).write_bytes(saved)
    ingest(archive, tmp_path)
    assert used_files(daily(db, 22)) == ["021", "022"]


@pytest.mark.xfail(
    strict=True,
    reason="issue #4: a file that arrives late is not used by the next day's document; "
    "--update cannot detect it because that document never recorded the file",
)
def test_late_file_is_used_by_the_next_day(db, archive, tmp_path):
    late_file_setup(db, archive, tmp_path)

    assert used_files(daily(db, 23)) == ["022", "023"]


def test_forced_update_makes_the_next_day_use_a_late_file(db, archive, tmp_path):
    late_file_setup(db, archive, tmp_path)

    run_collector(archive, tmp_path, "--update", "--force", "--file", str(day_file(archive, 23)), *ALL_OPTIONS)

    assert used_files(daily(db, 23)) == ["022", "023"]
    assert db.hourly_streams.count_documents({}) == 72
    assert orphans(db) == 0
