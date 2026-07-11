"""
PrimeNet Registry Test
"""

from core.registry import ObservatoryRegistry


class TestObservatory:
    name = "Test Observatory"
    status = "ready"

    def run(self, session=None):
        print("Test Observatory running.")
        return {
            "status": "success",
            "message": "Test Observatory completed.",
        }


def main():
    registry = ObservatoryRegistry()

    test_observatory = TestObservatory()
    registry.register(test_observatory)

    registry.summary()

    result = registry.run("Test Observatory")
    print(result)


if __name__ == "__main__":
    main()