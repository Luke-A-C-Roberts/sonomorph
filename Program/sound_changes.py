from re        import Match, Pattern, compile, finditer, search, split
from functools import reduce
from operator  import iconcat
from itertools import filterfalse
from random    import choice

from catagories import Catagories, Catagory


# sound change object used both for detecting contexts where a sound change can occur, and applying sound changes
class SoundChange:
    def __init__(self, catagories: Catagory, input_val: str, output_val: str, context: str, nontexts: list[str], metathesize: bool) -> None:
        self.input_val = input_val
        self.output_val= output_val
        self.context   = context
        self.nontexts  = nontexts

        self.is_epenthesis = input_val == ""
        self.is_metathesis = metathesize

        self.input_pattern = self.__compile_context_pattern(
            input_val, catagories
        )
        self.context_pattern = self.__compile_context_pattern(
            self.__substitute_into_context(context, input_val), catagories
        )
        self.nontext_patterns = [
            self.__compile_context_pattern(
                self.__substitute_into_context(nontext, input_val), catagories
            )
            for nontext in nontexts
        ]
        self.sub_context_patterns = [
            self.__compile_context_pattern(context_body, catagories)
            for context_body in context.split("_")
        ]

    # used to substitute the input into the context so that it can find matches
    def __substitute_into_context(self, context: str, value: str) -> str:
        return context.replace("_", value) if "_" in context else context

    # curlies are used for optionals which in regex is []?
    def __substitute_brackets(self, context: str) -> str:
        return context.replace("(", "[").replace(")", "]?")

    # substitutes the catagory strings into the regex
    def __substitute_catagories(self, context: str, catagories: Catagories) -> str:
        completed = ""
        for character in list(context):
            catagory = catagories[character]
            if catagory == None:
                completed += character
                continue
            completed += catagory
        return completed

    # ellipses are used for any number of character
    def __substitute_ellipses(self, context: str) -> str:
        return context.replace("...", ".*")

    def __substitute_wildcards(self, context: str) -> str:
        context = list(context)
        try:
            if context[0] == "*":
                context[0] = "."
        except:
            print(context)

        wildcard_positions: list[int] = []

        for position, character in enumerate(context):
            if position == 0:
                continue
            if character == "*" and context[position - 1] != ".":
                wildcard_positions.append(position)

        for wildcard_position in wildcard_positions:
            context[wildcard_position] == "."

        return "".join(context)

    # embeded brackets may cause issues for regex, so inner brackets are removed
    def __remove_higher_level_brackets(self, context: str) -> str:
        completed = ""
        current_level = 0
        for character in list(context):
            if character == "[":
                current_level += 1
            if not (character in "[]" and current_level > 1):
                completed += character
            if character == "]":
                current_level -= 1
        return completed

    # squares like SCA²
    def __replace_squares(self, context: str) -> str:
        completed = ""
        for character in list(context):
            completed += "{2}" if character == "²" else character
        return completed

    # compiles the pattern so it can be reused
    def __compile_context_pattern(self, context: str, catagories: Catagories) -> Pattern:
        context = self.__substitute_brackets(context)               # (X) -> [X]?
        context = self.__substitute_catagories(context, catagories) # X -> [xyz]
        context = self.__substitute_ellipses(context)               # ... -> .*
        context = self.__substitute_wildcards(context)              # * -> . (not before *)
        context = self.__remove_higher_level_brackets(context)      # [#[xyz]] -> [#xyz]
        context = self.__replace_squares(context)                   # x² -> x{2}
        return compile(context)

    # finds all of the inputs presesnt in the word
    def __obtain_input_matches(self, word: str) -> list[Match]:
        return list(finditer(self.input_pattern, word))

    # finds all of the contexts for the sound change
    def __obtain_context_matches(self, word: str) -> list[Match]:
        return list(finditer(self.context_pattern, word))

    # finds all of the nontexts (exceptions to contexts) for the sound change
    def __obtain_nontext_matches(self, word: str) -> list[Match]:
        nontext_matches = [
            list(finditer(nontext_pattern, word))
            for nontext_pattern in self.nontext_patterns
        ]
        return reduce(iconcat, nontext_matches, [])

    # filters sub context spans for non epenthesis sound changes so that inputs which are in sub contexts are not used
    def __obtain_sub_context_spans(self, context_matches: list[Match]) -> list[tuple[int]]:
        # filter out input matches that are also in a context body
        all_sub_context_spans: list[tuple[int]] = []
        for context_match in context_matches:
            context_str = context_match.group(0)
            start_pos = context_match.start()
            sub_context_spans: list[tuple[int]] = []

            # finds a match for each subcontext pattern and input pattern to extract position of each input_match
            for sub_context_pattern in self.sub_context_patterns:
                sub_context_match = search(sub_context_pattern, context_str)
                if not sub_context_match:
                    break

                context_str = context_str[:sub_context_match.end()]
                sub_context_spans.append(
                    (start_pos, start_pos + sub_context_match.end())
                )
                start_pos += sub_context_match.end()
                input_match = search(self.input_pattern, context_str)

                if not input_match:
                    break

                context_str = context_str[:input_match.end()]

            all_sub_context_spans.append(sub_context_spans)

        all_sub_context_spans = [
            span for span in reduce(iconcat, all_sub_context_spans, [])
        ]
        return all_sub_context_spans

    # used for when there is an epenthesis to find the correct places in a SC context to use
    def __obtain_epenthesis_spans(self, context_matches: list[Match]) -> list[tuple[int]]:
        all_sub_context_spans: list[tuple[int]] = []
        for context_match in context_matches:
            context_str = context_match.group(0)
            start_pos = context_match.start()
            sub_context_spans: list[tuple[int]] = []
 
            # finds a match for each subcontext pattern to extract position of a gap between sub_contexts
            for sub_context_pattern in self.sub_context_patterns:
                sub_context_match = search(sub_context_pattern, context_str)
                if not sub_context_match:
                    break

                context_str = context_str[:sub_context_match.end()]

                sub_context_spans.append(
                    (start_pos, start_pos + sub_context_match.end())
                )
                start_pos += sub_context_match.end()

            all_sub_context_spans.append(sub_context_spans)

        all_sub_context_spans = [
            span for span in reduce(iconcat, all_sub_context_spans, [])
        ]
        return all_sub_context_spans

    # used to find if an input match is inside of a context match. used to select which contexts to SC
    def __is_in_context(self, input_match: Match, context_match: Match) -> bool:
        return context_match.start() <= input_match.start() and input_match.end() <= context_match.end()

    # finds if an input is in a sub context span
    def __is_in_sub_context(self, input_match: Match, sub_context_span: tuple[int]) -> bool:
        if input_match.start() == input_match.end():
            return True
        return sub_context_span[0] <= input_match.start() and input_match.end() <= sub_context_span[1]

    # obtains the positions of contexts that match the pattern but not which also match any nontexts
    def __obtain_valid_matches(self, word: str) -> list[Match]:

        input_matches = self.__obtain_input_matches(word)
        context_matches = self.__obtain_context_matches(word)
        nontext_matches = self.__obtain_nontext_matches(word)

        # lambda for filtering which input matches are inside context matches
        def is_in_context_lmd(input_match): return any(
            self.__is_in_context(input_match, context_match) for context_match in context_matches
        )

        # similar lamda for nontexts
        def is_in_nontext_lmd(input_match): return any(
            self.__is_in_context(input_match, nontext_match) for nontext_match in nontext_matches
        )

        input_matches = list(filter(
            is_in_context_lmd, input_matches
        )) # filter those that match a context

        input_matches = list(filterfalse(
            is_in_nontext_lmd, input_matches
        )) # filter thoes that are not in a nontext

        # for when there is a epenthesis (input is "")
        if self.input_val == "":
            all_epenthesis_spans = self.__obtain_epenthesis_spans(
                context_matches)

            # lambda used to filter which inputs are epenthesis
            def is_similar_sub_context_lmd(input_match): return any(
                epenthesis_span[1] == input_match.end()
                for epenthesis_span in all_epenthesis_spans
            )
        
            # filters which inputs are epenthesis
            valid_matches = list(filter(
                is_similar_sub_context_lmd, input_matches
            ))
            return valid_matches

        all_sub_context_spans = self.__obtain_sub_context_spans(
            context_matches
        )

        # lambda for seeing which input are inside a sub context
        def is_in_sub_context_lmd(input_match): return any(
            self.__is_in_sub_context(input_match, sub_context_span)
            for sub_context_span in all_sub_context_spans
        )
        
        # filters inputs which are not in sub contexts
        valid_matches = list(filterfalse(
            is_in_sub_context_lmd, input_matches
        ))

        return valid_matches

    # generate_normal_output
    def __generate_normal_output(self, input_match_string: str, catagories: Catagories) -> str:
        i_str = self.__substitute_catagories(self.input_val, catagories)
        i_str = self.__remove_higher_level_brackets(i_str)
        i_str = self.__replace_squares(i_str)

        o_str = self.__substitute_catagories(self.output_val, catagories)
        o_str = self.__remove_higher_level_brackets(o_str)
        o_str = self.__replace_squares(o_str)
        
        i_substr_catagories = list(finditer(r"\[[^\[\]]+\]", i_str))             # [abc]de[fg] -> [abc] [fg]
        i_substr_double_catagories = list(finditer(r"\[[^\[\]]+\]\{2\}", i_str)) # [abc]{2}def -> [abc]{2}

        o_substr_catagories = list(finditer(r"\[[^\[\]]+\]", o_str))
        o_substr_double_catagories = list(finditer(r"\[[^\[\]]+\]\{2\}", o_str))

        def in_substr_double_catagory(substr_catagory: Match, substr_double_catagories: list[Match]): return any([
            substr_catagory.start() == substr_double_catagory.start()
            for substr_double_catagory in substr_double_catagories
        ])

        i_substr_catagories = list(filterfalse(
            lambda i_substr_catagory: in_substr_double_catagory(i_substr_catagory, i_substr_double_catagories),
            i_substr_catagories
        ))

        o_substr_catagories = list(filterfalse(
            lambda o_substr_catagory: in_substr_double_catagory(o_substr_catagory, o_substr_double_catagories),
            o_substr_catagories
        ))

        i_search_matches: list[Match] = sorted(
            i_substr_catagories + i_substr_double_catagories,
            key=lambda this_match: this_match.start()
        )

        o_search_matches: list[Match] = sorted(
            o_substr_catagories + o_substr_double_catagories,
            key=lambda this_match: this_match.start()
        )

        if len(o_search_matches) > len(i_search_matches):
            raise(ValueError("there are more output_catagories than input_catagories"))

        if len(o_search_matches) == 0:
            return self.output_val

        i_non_search_matches: list[str] = []
        i_str_copy = i_str
        for i_search_match in i_search_matches:
            i_str_copy.replace(i_search_match.group(0), "_")
        i_non_search_matches = i_str_copy.split("_").remove("")
        
        input_match_catagory_matches = [input_match_string]
        for non_search_match in i_non_search_matches:
            input_match_catagory_matches[-1].split(non_search_match)
            reduce(iconcat, input_match_catagory_matches, [])

        input_match_catagory_matches.remove("")

    # generate_metathesis_output
    def __generate_metathesis_output(self, input_match_string: str, catagories: Catagories) -> str:
        raise NotImplementedError("metathesis is not implemented")

    # generates an output based on notation
    def __generate_output(self, input_match_string: str, catagories: Catagories) -> str:
        if self.is_metathesis:
            return self.__generate_metathesis_output(input_match_string, catagories)

        return self.__generate_normal_output(input_match_string, catagories)

    # applies the SC to a word
    def apply_to(self, word: str, catagories: Catagories) -> str:
        # add word endings and get the input matches
        word = f"#{word}#"
        valid_matches = self.__obtain_valid_matches(word)

        match_positions = [[
                i for i in range(this_match.start(), this_match.end())
            ] for this_match in valid_matches
        ]
        match_positions = set(reduce(iconcat, match_positions, []))
        literal_positions = list(
            set(range(len(word))).difference(match_positions)
        )
        substitute_positions = [
            this_match.start() for this_match in valid_matches
        ]

        new_word = ""
        for position, character in enumerate(word):
            if self.is_epenthesis and position in literal_positions and position in substitute_positions:
                this_match = [
                    valid_match for valid_match in valid_matches
                    if valid_match.start() == position
                ][0]
                new_word += self.__generate_output(
                    this_match.group(0), catagories
                ) + character
                continue

            if position in literal_positions:
                new_word += character
                continue

            if not position in substitute_positions:
                continue

            this_match = [
                valid_match for valid_match in valid_matches
                if valid_match.start() == position
            ][0]

            new_word += self.__generate_output(
                this_match.group(0), catagories
            )

        return new_word[1:-1]


# converts notation to a SoundChange object
def notation_to_SC(catagories: Catagories, notation: str) -> SoundChange:
    sections = notation.split("/")
    if len(sections) < 3:
        raise ValueError(
            "notation must be in the form <input>/<output>/<context>[/<nontext_1>/<nontext_2>/.../<nontext_N>]"
        )

    if len(sections) == 3:
        return SoundChange(catagories, sections[0], sections[1], sections[2], [], False)

    return SoundChange(catagories, sections[0], sections[1], sections[2], sections[3:], False)


# holds and applies sound changes
class SoundChanges:
    pass