# Source verification

`source-audit.json` was generated from the original version-2 CSV files, downloaded from [Griko Nibras's Kaggle dataset](https://www.kaggle.com/datasets/grikomsn/amazon-cell-phones-reviews/versions/2). The publisher lists CC0. Raw files stay outside version control.

The inspected files contain 720 listings and 67,986 review rows, with 12 empty bodies and 1,095 repeated listing/body combinations after case and whitespace normalisation. The dates span 24 November 2003 to 25 December 2019. None of those counts describes a ready-to-train ABSA dataset: aspect labels are absent.

The explicit listing selection in `config/products.json` keeps smartphone models and distinguishes renewed listings. It is a bounded historical demonstration corpus. It is not a sample of current phone availability or a representative brand ranking. Language identification and exact deduplication have known limits, so their counts and policy are stored in the generated preparation manifest.
