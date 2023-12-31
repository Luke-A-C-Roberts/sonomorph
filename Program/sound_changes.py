from re        import Match, Pattern, compile, finditer, search
from functools import reduce
from operator  import iconcat
from itertools import filterfalse
from random    import choice

from catagories import Catagories, Catagory

# sound change object used both for detecting contexts where a sound change can occur, and applying sound changes
class SoundChange:
    def __init__(self, catagories: Catagories, input_val: str, output_val: str, context: str, nontexts: list[str], metathesize: bool) -> None:
        self.input_val = input_val
        self.output_val= output_val
        self.context   = context
        self.nontexts  = nontexts

        # bools for SC type
        self.is_epenthesis = input_val == ""
        self.is_metathesis = metathesize

        # formats input and output for generation of output based on input
        self.i_str = self.__substitute_catagories(self.input_val, catagories)
        self.i_str = self.__remove_higher_level_brackets(self.i_str)
        self.i_str = self.__replace_squares(self.i_str)
        self.o_str = self.__substitute_catagories(self.output_val, catagories)
        self.o_str = self.__remove_higher_level_brackets(self.o_str)
        self.o_str = self.__replace_squares(self.o_str)

        # regex pattern object generation for searching
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

    # 2D list flattened to 1D list
    def __flatten_list(self, l: list[list[any]] | list[tuple[any]]) -> list[any]:
        return reduce(iconcat, l, [])

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
            return context

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

    # used to see if there is a problem with overlapping regex
    def __same_affixes(self, s: str) -> str:
        # hello -> he lo,  friend -> fri end
        size  = len(s) // 2
        start = [s[:i] for i in range(1, size+1)]
        end   = [s[-i:] for i in range(1, size+1)]
        for x in zip(start, end):
            if x[0] == x[1]: return x[0]
        return ""

    # method for gernerating multiple overlapping patterns
    def __overlapping_finditer(self, r: Pattern, s: str):
        is_same_affixes = self.__same_affixes(r.pattern)
        if is_same_affixes == "": return finditer(r,s)
        blank_len = len(r.pattern) - len(is_same_affixes)
        results = []
        while True:
            result = list(r.finditer(s))
            if result == []: break
            for match in result:
                s = list(s)
                index = match.start()
                for s_index in range(index, index + blank_len):
                    if s_index < len(s):
                        s[s_index] = "_"
                s = ''.join(s)
            results += result
        return iter(results)

    # finds all of the contexts for the sound change
    def __obtain_context_matches(self, word: str) -> list[Match]:
        return list(self.__overlapping_finditer(self.context_pattern, word))

    # finds all of the nontexts (exceptions to contexts) for the sound change
    def __obtain_nontext_matches(self, word: str) -> list[Match]:
        nontext_matches = [
            list(self.__overlapping_finditer(nontext_pattern, word))
            for nontext_pattern in self.nontext_patterns
        ]
        return self.__flatten_list(nontext_matches)

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

        return  self.__flatten_list(all_sub_context_spans)

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

        return self.__flatten_list(all_sub_context_spans)

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


        # finds the substring catagories
        i_substr_catagories = list(finditer(r"\[[^\[\]]+\]", self.i_str))             # [abc]de[fg] -> [abc] [fg]
        i_substr_double_catagories = list(finditer(r"\[[^\[\]]+\]\{2\}", self.i_str)) # [abc]{2}def -> [abc]{2}
        o_substr_catagories = list(finditer(r"\[[^\[\]]+\]", self.o_str))
        o_substr_double_catagories = list(finditer(r"\[[^\[\]]+\]\{2\}", self.o_str))

        # filters all catagories that are also doubles
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

        #sorts the io catagory matches
        i_search_matches: list[Match] = sorted(
            i_substr_catagories + i_substr_double_catagories,
            key=lambda this_match: this_match.start()
        )
        o_search_matches: list[Match] = sorted(
            o_substr_catagories + o_substr_double_catagories,
            key=lambda this_match: this_match.start()
        )

        # checks a SC to see if there are more output than input catagories
        # having more output catagories doesn't work since there's nothing to substitute
        if len(o_search_matches) > len(i_search_matches):
            raise(ValueError("there are more output catagories than input catagories"))

        # if there are no output catagories their is no need for substitution so the output is given
        if len(o_search_matches) == 0:
            return self.output_val

        i_non_search_matches: list[str] = []

        # replaces catagories with _ so they can be replaced
        o_str_cpy = self.o_str
        for o_search_match in o_search_matches:
            match_str = o_search_match.group(0)
            o_str_cpy = o_str_cpy.replace(match_str, "_")

        # splits input into a template for output, keeping "_" seperate eg. "a_ka" -> ["a", "_", "ka"]
        o_template: list[str] = []
        temp_str = ""
        for character in list(o_str_cpy):
            if character == "_":
                o_template.append(temp_str)
                temp_str = ""
                o_template.append("_")
                continue
            temp_str += character

        o_template = list(filterfalse(lambda string: string == "", o_template))

        # finds the characters that correspond to catagories in the input match
        input_match_catagory_matches = [input_match_string]
        for non_search_match in i_non_search_matches:
            input_match_catagory_matches[-1].split(non_search_match)
            self.__flatten_list(input_match_catagory_matches)

        # builds a structure which is used to match input, input catagory and output catagory
        io_catagory_strs = [
            self.__flatten_list(list(input_match_catagory_matches[0])),
            [ism.group(0) for ism in i_search_matches],
            [osm.group(0) for osm in o_search_matches]
        ]

        # generates output
        output = ""
        io_catagory_pos = 0
        for o_substring in o_template:
            if o_substring == "_":
                input_character = io_catagory_strs[0][io_catagory_pos]
                input_pos = list(io_catagory_strs[1][io_catagory_pos]).index(input_character)
                output_character = list(io_catagory_strs[2][io_catagory_pos])[input_pos]
                output += output_character
                io_catagory_pos += 1
                continue
            output + o_substring

        return output

    # generate_metathesis_output
    def __generate_metathesis_output(self, input_match_string: str, catagories: Catagories) -> str:
        start = input_match_string[0]
        end   = input_match_string[1]
        return end + start

    # generates an output based on notation
    def __generate_output(self, input_match_string: str, catagories: Catagories) -> str:
        if self.is_metathesis:
            return self.__generate_metathesis_output(input_match_string, catagories)

        return self.__generate_normal_output(input_match_string, catagories)

    # applies the SC to a word
    def __apply_single_SC(self, word: str, valid_matches: list[Match], catagories: Catagories) -> str:

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

        return new_word

    def apply_to(self, word: str, catagories: Catagories) -> str:
        word = f"#{word}#"

        while True:
            valid_matches = self.__obtain_valid_matches(word)
            if valid_matches == []: break
            word = self.__apply_single_SC(word, valid_matches, catagories)
            if self.input_val == "": break
            if self.i_str in self.o_str: break

        return word[1:-1]


# converts notation to a SoundChange object
def notation_to_SC(notation: str, catagories: Catagories) -> SoundChange:
    is_metathesis = False
    if search("..+/\\\\\\\\/", notation): # suprisingly if this is inputted it looks like "ab/\\/"
        sections = ''.join([c for c in list(notation) if c != "\\"]).split("/")
        is_metathesis = True
    else:
        sections = notation.split("/")

    if len(sections) < 3: raise ValueError(
        "notation must be in the form <input>/<output>/<context>[/<nontext_1>/<nontext_2>/.../<nontext_N>]"
    )

    return SoundChange(
        catagories,
        sections[0],
        [] if is_metathesis else sections[1],
        sections[2],
        [] if len(sections) == 3 else sections[3:],
        is_metathesis
    )

# holds and applies sound changes
class SoundChanges:
    def __init__(self, notations: list[str], catagories: Catagories) -> None:
        self.notations = notations
        self.SCs = [notation_to_SC(notation, catagories) for notation in notations]

    def apply_all(self, words: list[str], catagories: Catagories) -> list[str]:
        for index, word in enumerate(words):
            for SC in self.SCs:
                word = SC.apply_to(word, catagories)
            words[index] = word
        return words
