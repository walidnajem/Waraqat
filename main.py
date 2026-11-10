import sys
import traceback

if __name__ == "__main__":
    try:
        from gui import App
        app = App()
        app.mainloop()
    except Exception as e:
        print("\n" + "=" * 50)
        print("Error starting Waraqat | ورقات:")
        traceback.print_exc()
        print("=" * 50)
        try:
            input("\nPress Enter to exit...")
        except Exception:
            pass
        sys.exit(1)
