from catagories    import Catagory, Catagories
from sound_changes import SoundChange, notation_to_SC


# used to debug applying sound changes to words
class SCTest:
    def __init__(self, notation: str, test_words: str | list[str], output_words: str | list[str]) -> None:
        self.notation = notation

        # test words can either be single string or list of strings
        self.test_words = [test_words] if type(
            test_words
        ) == type(str) else test_words

        self.output_words = [output_words] if type(
            output_words
        ) == type(str) else output_words

        # make sure the number of input/output words match
        if len(test_words) != len(output_words):
            raise ValueError(
                "test and output word lists must be the same length"
            )

    # gets the number of test words
    def get_test_words_len(self):
        return len(self.test_words)

    # tests to see if the SC applier works as intended and prints the results
    def test(self, catagories: Catagories, test_index: int = 0, show_success: bool = True) -> tuple[bool, int]:
        all_successful = True
        number_successful = 0

        SC = notation_to_SC(self.notation, catagories) # conversion of noation into SC object

        heading_buffer = "#" * (77 - len(f"Testing {self.notation}"))
        print(f"\033[0;34m# Testing {self.notation} {heading_buffer}\033[0m")

        # every test word is applied and then compared to the intended output
        for index, (test_word, output_word) in enumerate(zip(self.test_words, self.output_words)):
            new_word = SC.apply_to(test_word, catagories)

            if new_word == output_word:
                if show_success:
                    print (
                        f"{index + test_index} \033[1;32mTest Successful\033[0m:\t{test_word}\t->\t{new_word}"
                    )
                number_successful += 1
                continue
            print (
                f"{index + test_index} \033[1;31mTest Unsuccessful\033[0m:\t{test_word}\t->\t{new_word}, expected {output_word}"
            )
            all_successful = False

        foot_buffer = "#" * 80
        print(f"\033[0;34m{foot_buffer}\033[0m\n")

        return (all_successful, number_successful)


# allows multiple numbered sound change tests at once
def test_multiple_SCs(SC_tests: list[SCTest], catagories: Catagories, show_success: bool = True) -> None:
    number_words_successful = 0
    number_SCs_successful = 0

    SC_count = len(SC_tests)
    word_count = sum([SC_test.get_test_words_len() for SC_test in SC_tests])

    SC_test_number = 0
    for SC_test in SC_tests:
        test_results = SC_test.test(catagories, SC_test_number, show_success)
        SC_test_number += SC_test.get_test_words_len()
        number_SCs_successful += 1 if test_results[0] else 0
        number_words_successful += test_results[1]

    print(f"{number_words_successful} / {word_count} words successful.")
    print(f"{number_SCs_successful} / {SC_count} SCs successful.")
