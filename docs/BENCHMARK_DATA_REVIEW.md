# Alternative labelled datasets — decision record

Checked on 19 October 2026 while reducing the annotation burden for the solo implementation. The application needs English sentences with all ten category states, including absent. A downloadable phone dataset is useful only if its annotation coverage supports those claims.

| Candidate | Evidence checked | Decision |
| --- | --- | --- |
| iPhone 11 dataset described by Chehal, Gupta and Gulati | The paper describes 960 reviews, 2,109 cleaned sentences, predefined feature categories and manual annotation. | Relevant research candidate. No machine-readable label archive was linked in the article inspected. It cannot currently supply a reproducible local benchmark. |
| UIC additional review datasets, nine products | Downloaded the archive from the researcher's page and inspected its Nokia 6600 file: 49 review boundaries and native feature/polarity annotations. | Useful legacy material, with a different annotation scheme. It is not substituted for the frozen application study. |

The iPhone article is [Evaluating Annotated Dataset of Customer Reviews for Aspect Based Sentiment Analysis](https://journals.riverpublishers.com/index.php/JWE/article/view/6205), DOI 10.13052/jwe1540-9589.2122. Its published metrics belong to that study; none are reported as our results. A paper's example table does not replace the full underlying dataset or establish permission to redistribute it.

The UIC source is [Bing Liu's sentiment-analysis dataset page](https://www.cs.uic.edu/~liub/FBS/sentiment-analysis.html), under the annotated nine-product collection associated with Ding, Liu and Yu, WSDM 2008. Its [original archive](https://www.cs.uic.edu/~liub/FBS/Reviews-9-products.rar) was inspected locally, without executing anything. It is not copied into this repository. No general redistribution licence was established from the inspected listing.

The legacy file labels native targets, including device-level, carrier and service opinions. Our categories combine different concepts. Mapping an explicitly labelled camera opinion is possible; declaring every other application category absent would introduce unsupported gold labels. Comparative targets, implicit references and annotation scope also need review. A narrow mapped diagnostic could be reported separately in future, with its own denominator and limitations; it would not establish full ten-category performance on the current corpus.

The selected route uses the frozen local study and a disclosed training-only pseudo-labelled set. The user later requested AI validation annotation; the resulting 1-human/34-AI-assisted validation reference is used only as an explicitly labelled diagnostic. The 69 test sentences remain reserved for independent human evaluation. The small reference and mixed annotation origins limit the conclusions; see [current results](RESULTS.md).
