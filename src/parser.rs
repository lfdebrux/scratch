use peg;

peg::parser!{
    grammar rcsh_parser() for str {

        // whitespace
        rule _() = quiet!{ [' ' | '\t'] }

        // TODO: replace String with string slices &str (need to think about lifetimes though)

        // ## Atoms

        // The following characters have special meanings:
        rule chr() = !['#' | '$' | '|' | '&' | ';' | '(' | ')' | '<' | '>' | ' ' | '\t' | '\n'] [_]

        // Special characters terminate words
        pub rule word_unquoted() -> String = w:$(chr()+) { w.to_string() }

        // The single quote prevents special treatment of any character other than itself
        pub rule word_quoted() -> String = "'" s:$((!"'" [_])*) "'" { s.to_string() }

        pub rule word() -> String = word_quoted() / word_unquoted()


        // ## Lists

        // The primary data structure is the list, which is a sequence of words
        pub rule list() -> Vec<String>
            = word() ** _


        // identifiers
        pub rule name() -> String
            = n:$(['a'..='z' | 'A'..='Z' | '0'..='9' | '%' | '*' | '_' | '-']+) { n.to_string() }


        // statements
        pub rule assignment() -> (String, Vec<String>)
            = n:name() _ "=" _ x:list() { (n, x) }

        pub rule command() -> (String, Vec<String>)
            = n:name() _ x:list() { (n, x) }

    }
}

#[cfg(test)]
mod tests {
    // use std::fs;
    use super::*;

    // from https://stackoverflow.com/questions/38183551
    macro_rules! string_vec {
        ($($x:expr),*) => (vec![$($x.to_string()),*]);
    }

    #[test]
    fn name() {
        assert!(rcsh_parser::name("hello").is_ok());
        assert!(rcsh_parser::name("%read").is_ok());
        assert!(rcsh_parser::name("do_this").is_ok());
        assert!(rcsh_parser::name("_private").is_ok());
        assert!(rcsh_parser::name("a1").is_ok());

        assert!(rcsh_parser::name("c$").is_err());
        assert!(rcsh_parser::name("path/name").is_err());
    }

    #[test]
    fn assignment() {
        assert_eq!(rcsh_parser::assignment("a = 1"), Ok((String::from("a"), string_vec!["1"])));
        assert_eq!(rcsh_parser::assignment("list = a b c"), Ok((String::from("list"), string_vec!["a", "b", "c"])));
        assert_eq!(rcsh_parser::assignment("s = 'Hello world'"), Ok((String::from("s"), string_vec!["Hello world"])));
        assert_eq!(
            rcsh_parser::assignment("hello = Hello 'Laurence de Bruxelles'"),
            Ok((String::from("hello"), string_vec!["Hello", "Laurence de Bruxelles"]))
        );
    }

    #[test]
    fn list() {
        assert_eq!(rcsh_parser::list("1"), Ok(string_vec!["1"]));
        assert_eq!(rcsh_parser::list("a b c"), Ok(string_vec!["a", "b", "c"]));
        assert_eq!(rcsh_parser::list("'Hello world'"), Ok(string_vec!["Hello world"]));
        assert_eq!(
            rcsh_parser::list("Hello 'Laurence de Bruxelles'"),
            Ok(string_vec!["Hello", "Laurence de Bruxelles"])
        );
    }

    #[test]
    fn string() {
        assert_eq!(rcsh_parser::word_quoted("'Hello world'"), Ok(String::from("Hello world")));
    }

    /*
    #[test]
    fn comments() {
        assert_eq!(rcsh_parser::lines("# Hello World"), Ok(vec![1]));
        assert_eq!(rcsh_parser::lines("# Hello World\n# 2nd line"), Ok(vec![1, 1]));
    }

    #[test]
    fn hello() {
        let script = fs::read_to_string("examples/hello.rcsh")
            .expect("could not read test file");

        println!("{}", script)
    }
    */
}
