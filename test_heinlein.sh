OPTIND=1
while getopts 'i' opt; do
  case $opt in
    i)
      CMD="/bin/bash"
      ;;
    *)
      CMD=""
      ;;
  esac
done

docker build -t heinlein-test:latest --platform linux/x86-64 . && docker run -v $HEINLEIN_TEST_DATA:/home/data -it heinlein-test:latest $CMD
