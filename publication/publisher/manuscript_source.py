APPENDIX_TITLES = (
    "Appendix A. Canonical Tables",
    "Appendix B. Theory-Validation Dataset Summary",
)

def section_paragraphs(stats):
    return [
        {"title":"1. Introduction","figure":"fig01_evolution","paragraphs":[
            "Computational methods have become an indispensable component of modern scientific research. Across disciplines, large-scale computational investigations increasingly generate data products, software artifacts, metadata, and derived observations that must be organized if they are to remain useful after the original computation has completed.",
            "Computational arithmetic presents a similar engineering challenge. Researchers may repeatedly generate prime data, verify files, write analysis scripts, and preserve outputs in project-specific formats. PrimeNet was developed to reduce this duplication by organizing computational arithmetic as persistent scientific infrastructure.",
            "The purpose of this paper is to document the PrimeNet reference architecture. The contribution is architectural rather than mathematical: PrimeNet provides an implemented framework for deterministic repository construction, canonical observational coordinates, reusable observatories, persistent products, and publication support."
        ]},
        {"title":"2. Design Philosophy","table":"table02_design_principles","paragraphs":[
            "PrimeNet was not designed all at once. Its architectural principles emerged through the practical engineering process of building, verifying, organizing, and reusing large-scale prime computation. The resulting design favors stable interfaces, separation of responsibilities, deterministic construction, and reusable scientific products.",
            "A central principle is observation before explanation. PrimeNet does not require a specific conjecture or theoretical model before computation can begin. Instead, it provides a systematic environment in which observations can be generated, recorded, compared, and reused.",
            "The architecture also treats reproducibility as a structural requirement. Verification, metadata, sessions, registries, and publication manifests are not optional decorations; they are part of the system design."
        ]},
        {"title":"3. Prime Space","figure":"fig03_prime_space","paragraphs":[
            "Prime Space is the canonical coordinate system used by PrimeNet. Instead of treating prime numbers only as numerical values, PrimeNet records observations using the prime index together with the prime value. This gives each observed prime a stable coordinate within the ordered sequence of primes.",
            "The prime index is important because many observational products concern relationships between successive primes, prime gaps, fixed-gap languages, transition structures, and other sequence-based phenomena. Using a canonical coordinate system makes these products easier to compare and reproduce.",
            "Prime Space therefore acts as an organizing layer between raw arithmetic computation and higher-level observation. It is the coordinate foundation upon which repositories, observatories, and products can agree."
        ]},
        {"title":"4. Repository Architecture","figure":"fig04_repository","table":"table04_repository_statistics","paragraphs":[
            "The Repository is the persistent computational foundation of PrimeNet. It stores verified computational assets in a form that can be reused by observatories and future investigations without regenerating the same data repeatedly.",
            "The reference implementation covers the interval {repository_interval}, contains {verified_prime_numbers} verified prime numbers, and is organized into {repository_segments} independently verified repository segments. These values serve as architectural evidence that the repository model has been realized at substantial scale.",
            "Repository services separate access, metadata, verification, and persistent storage. This separation allows the repository to remain stable while services and observatories evolve above it."
        ]},
        {"title":"5. Repository Construction and Verification","figure":"fig05_construction","paragraphs":[
            "Repository construction proceeds through deterministic segmentation, prime generation, segment persistence, and independent verification. Each segment becomes part of the persistent repository only after passing verification.",
            "This workflow is intentionally conservative. The goal is not merely to compute primes, but to create computational assets that can be trusted and reused. A verified segment is treated as a persistent scientific resource rather than a temporary output file.",
            "The construction and verification model also supports incremental growth. New ranges can be appended while previously verified segments remain stable."
        ]},
        {"title":"6. Observatory Framework","figure":"fig06_repository_scale","table":"table03_architectural_components","paragraphs":[
            "The Observatory Framework defines how scientific investigations are performed in PrimeNet. An observatory operates on repository assets, records an observation session, generates computational products, and may contribute to an atlas.",
            "This structure separates persistent computational data from observational logic. New observatories can be added without changing the repository, and existing products can be reused by future observatories.",
            "Observation Sessions preserve execution context and provenance. Products are therefore not isolated files but traceable outputs of a defined computational process."
        ]},
        {"title":"7. Products and Atlases","paragraphs":[
            "Products are persistent outputs generated by observatories. They may include tables, summaries, transition data, entropy measurements, figures, manifests, or other structured computational artifacts.",
            "Atlases organize related products into reusable scientific collections. The atlas concept reflects the view that computational observations should accumulate over time instead of disappearing after individual experiments.",
            "Products and atlases are essential to PrimeNet because they convert computational work into reusable scientific memory."
        ]},
        {"title":"8. Software Architecture","figure":"fig07_validation","table":"table05_software_modules","paragraphs":[
            "PrimeNet is implemented as a modular software system. Repository services, metadata services, product services, observatory execution, and publication support are separated into distinct responsibilities.",
            "This modularity is important for long-term maintainability. A new observatory should not need to reimplement repository access, metadata recording, product organization, or publication formatting.",
            "The software architecture follows a simple rule: each subsystem should reduce the manual work required by the next subsystem."
        ]},
        {"title":"9. Reproducibility and Publication Support","table":"table06_reproducibility_features","paragraphs":[
            "Reproducibility in PrimeNet is supported by deterministic construction, independent verification, structured metadata, observation sessions, persistent products, registries, and publication manifests.",
            "PrimeNet Publisher extends the reproducibility principle into scientific communication. It generates figures, tables, manuscript scaffolds, review reports, and publication manifests from structured sources.",
            "The publication system is included not as a convenience feature, but as part of the same engineering philosophy: computational knowledge should remain synchronized with the way it is communicated."
        ]},
        {"title":"10. Architectural Validation","figure":"fig08_performance","table":"table07_observational_performance","paragraphs":[
            "Architectural validation in this paper does not mean proving a theorem about primes. It means demonstrating that the proposed architecture has been implemented and exercised at meaningful scale.",
            "The repository interval, number of verified primes, number of repository segments, verification status, and largest stored prime are used as evidence that the architecture is concrete rather than aspirational.",
            "The accepted 1–3T twin-prime census provides additional operational evidence. PrimeNet processed {twin_total_gaps} gap records across {twin_partitions} partitions in {twin_end_to_end_runtime_min} minutes end to end. In the conservative steady-state window, the system sustained {steady_gaps_per_sec} gap observations per second with a runtime coefficient of variation of {steady_runtime_cv_percent}.",
            "These measurements are reported as implementation evidence rather than mathematical claims. They demonstrate that the persistent repository architecture can support stable, large-scale observational scans while preserving explicit provenance and runtime accounting."
        ]},
        {"title":"11. Validation Against Classical Number Theory",
         "figures":[
             "fig11_prime_count_comparison",
             "fig12_prime_count_relative_error",
             "fig13_mean_gap_validation",
             "fig13b_mean_gap_ratio",
             "fig14_twin_prime_validation",
             "fig14b_twin_prime_relative_error",
         ],
         "table":"table08_classical_validation",
         "paragraphs":[
            "A computational infrastructure for prime arithmetic should reproduce established finite-domain consequences of classical analytic number theory before it is used to support less familiar observational studies. PrimeNet therefore compares exact repository products with standard asymptotic reference functions for prime counts, mean gaps, and twin-prime counts.",
            "At x = {theory_endpoint_x}, the exact cumulative prime count is {theory_exact_prime_count}. The elementary prime-number-theorem approximation x/log(x) has relative error {theory_pnt_error_percent}, whereas Li(x) and the Riemann R function have relative errors {theory_li_error_percent} and {theory_riemann_r_error_percent}, respectively.",
            "The final partition has observed mean outgoing gap {theory_mean_gap}, compared with log(partition midpoint) = {theory_log_midpoint}; their ratio is {theory_mean_gap_ratio}. The cumulative twin-prime census is {theory_exact_twin_count}, compared with the Hardy–Littlewood prediction {theory_hl_prediction}, with finite-domain relative discrepancy {theory_hl_error_percent}.",
            "These comparisons are validation tests, not proofs and not claims of new asymptotic theory. Their role is to show that independently generated PrimeNet products agree closely with established large-scale expectations across the verified 1–3T repository."
        ]},
        {"title":"12. Discussion","figure":"fig09_growth","paragraphs":[
            "PrimeNet changes the role of computation in prime arithmetic from isolated calculation toward persistent infrastructure. The repository preserves computational assets, observatories preserve methods of investigation, products preserve results, and the Publisher preserves communication artifacts.",
            "The architecture does not attempt to solve open problems in prime arithmetic. Instead, it attempts to make future computational investigations easier to perform, easier to reproduce, and easier to build upon.",
            "The classical-validation results add an independent scientific check: exact products derived from the architecture recover established prime-count, gap-growth, and twin-prime behavior over the complete verified finite domain.",
            "This distinction remains central to the paper. PrimeNet is not presented as a new theory of primes, but as an engineered foundation for observational computational arithmetic."
        ]},
        {"title":"13. Future Directions","figure":"fig10_observatory","paragraphs":[
            "Future development may extend the repository, add new observatories, enrich product formats, build additional atlases, and improve publication workflows. These extensions do not require changing the core architectural idea.",
            "The Theory Validation Atlas can grow to include selected-gap spectra, maximal-gap behavior, Goldbach observatories, prime k-tuples, cross-scale comparisons, and other independently reproducible validation modules.",
            "A natural long-term goal is community extension. If future researchers can add observatories, reuse repository assets, and publish reproducible computational products with less duplicated engineering effort, then PrimeNet will have achieved its intended purpose.",
            "The value of scientific infrastructure is ultimately measured not by the infrastructure itself, but by the investigations it enables."
        ]},
        {"title":"14. Conclusion","paragraphs":[
            "PrimeNet is a reference architecture for persistent computational arithmetic. It organizes Prime Space, a verified repository, observatories, observation sessions, products, atlases, registries, and publication support into a unified system for reproducible computational investigation.",
            "The reference implementation demonstrates the architecture through a repository covering {repository_interval}, containing {verified_prime_numbers} verified prime numbers, and passing repository verification across {repository_segments} segments.",
            "Independent comparison with classical prime-count, mean-gap, and twin-prime reference laws further demonstrates that the exact observational products are scientifically coherent over the verified finite domain.",
            "The primary contribution of PrimeNet is not a new prime algorithm or mathematical theorem. It is an implemented architecture intended to help future researchers spend less time rebuilding computational infrastructure and more time doing science."
        ]},
    ]
