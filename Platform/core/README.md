# PrimeNet Platform Core

`Platform.core` is the canonical infrastructure layer for the PrimeNet
repository and prime-index coordinate system.

It is distinct from any historical or experimental root-level `core`
package. All internal imports must use the fully qualified package name:

```python
from Platform.core...