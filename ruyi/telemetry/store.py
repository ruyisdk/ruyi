class TelemetryStore:
    def __init__(self, store_dir: str, local: bool) -> None:
        self.store_dir = store_dir
        self.local = local
