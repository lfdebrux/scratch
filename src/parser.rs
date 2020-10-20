use peg;

peg::parser!{
    grammar rcsh_parser() for str {

        rule _() = quiet!{ [' ' | '\t'] }

        // TODO: replace String with string slices &str (need to think about lifetimes though)

        pub rule word() -> String = w:$((![' ' | '\t' | '\n' | ';'] [_])+) { w.to_string() }

        pub rule string() -> String = "'" s:$((!"'" [_])*) "'" { s.to_string() }

        pub rule list() -> Vec<String>
            = x:(string() / word()) ** _ { x }

        pub rule name() -> String
            = n:$(['a'..='z' | 'A'..='Z' | '0'..='9' | '%' | '*' | '_' | '-']+) { n.to_string() }

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
    fn string() {
        assert_eq!(rcsh_parser::string("'Hello world'"), Ok(String::from("Hello world")));
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
