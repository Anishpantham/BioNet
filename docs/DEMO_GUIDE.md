# Three-minute demonstration
0:00 Explain UDP's missing reliability and the added Selective Repeat mechanism.
0:20 Generate data with `python scripts/generate_test_data.py`.
0:35 Start `python -m bionet receiver --output received-demo`.
0:50 Run `python -m bionet sender --file data/synthetic.zip --verbose`.
1:15 Point out ACK sequence and SHA256 true. Compare hashes with
`shasum -a 256 data/synthetic.zip received-demo/synthetic.zip` (macOS/Linux).
1:35 Restart receiver with a fresh output directory and `--loss .1`.
Run sender with `--loss .2 --verbose`; explain selective retries.
2:20 Show JSON completion time and goodput; open results PNGs.
2:45 Explain CRC vs SHA256, privacy, limitations, and instructor approval.

For the final local demonstration, review code first; install on two trusted
machines, allow UDP 9000, bind receiver to its LAN address, and set sender host
to that address. Use `--file /local/private/25BCS126.zip`. Keep the real file
outside Git and cloud storage. Use a private output directory, compare streaming
SHA256 values, and retain only non-sensitive metrics. Never extract received
archives automatically. This real-dataset LAN demonstration remains pending.

Team roles: student 1 wire format/sender; student 2 receiver/integrity;
student 3 experiments/testing. All three should explain every protocol state.
