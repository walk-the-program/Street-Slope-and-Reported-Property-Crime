Dear Editors,

This is a Research Article and I would like you to consider it for PLOS ONE.

It started on a hill in Salt Lake City. I was walking up it, out of breath, doing the
thing where you accidentally price out a hypothetical you have no business thinking
about — in this case how genuinely miserable it would be to burgle any of the houses I
was walking past, and then carry anything at all back down again. It seemed like the
sort of thought somebody must already have had properly.

Somebody had, more or less. There is one sentence in Haberman and Kelsay's 2021 paper
in the *Journal of Quantitative Criminology*. They found that robberies drop as street
grade rises in Cincinnati, then closed by listing three things that might explain it:
the physical cost of offending, how hard steep blocks are to get away from, and the
fact that fewer people walk them. They did not test between the three, and as far as I
can tell nobody has since. That sentence is what this paper is about. I take the
outcome from robbery to property crime, the setting from one city to nine, and build a
design where those explanations predict different things.

To be upfront about novelty: the association itself is not new. Breetzke found something
like it in Tshwane, Kim and Wo in San Francisco, and two bicycle theft papers this year.
What earns publication, I think, is the combination — nine cities through one
standardized pipeline so they are actually comparable, a within-place comparison between
crimes that carry something away and crimes that do not, exposure denominators built
from counts of the real targets instead of census housing, and an unsparing account of
where the measurement goes wrong. The pooled estimate is −6.89% per degree of slope,
but the prediction interval for a new city runs from −13.7% to +0.5%, so the magnitude
does not travel and I say so.

I should be as clear about the limits. This is observational. Block group fixed effects
strip out everything that varies between neighborhoods and nothing that varies inside
one, and I do not claim anywhere that gradient deters anybody. Of the four mechanisms I
tested, exactly one is properly bounded: the idea that the effect is the metabolic cost
of hauling stolen goods, which an equivalence test rules out at half the headline
effect. The other three are narrowed rather than killed. The paper ends without
identifying the mechanism, which seemed more useful than inventing a fifth I had no way
to test.

There is also a fair amount here about what went wrong: four classifier defects found by
audit, a terrain threshold I picked after looking at the data and later demoted to a
sensitivity analysis, and one extension I retracted and re-ran after finding its models
had never converged. It is all itemized in S1 Appendix, and the headline estimates are
refit with independent software and agree to 8.3 × 10⁻⁷.

Code, panels, result tables and the classifier validation set are public at
https://github.com/walk-the-program/Street-Slope-and-Reported-Property-Crime. This is
not under consideration anywhere else, I have not submitted it to PLOS before, and there
are no related submissions. No competing interests, no funding, sole author. Any
Academic Editor working in environmental criminology, crime and place, or spatial
analysis of urban form would suit, and I am not opposing any reviewers.

Thank you for reading it.

Walker Tracy
Independent Researcher, Salt Lake City, Utah
walkeratracy@gmail.com
