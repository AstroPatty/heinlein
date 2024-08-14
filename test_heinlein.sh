while getopts 'is:' opt; do
  case $opt in
    i)
      CMD="/bin/bash"
      TEST_SET=""
      ;;
    s)
      TEST_SET="-e TEST_SET=$OPTARG"
      ;;
    *)
      CMD=""
      ;;
  esac
done

docker build -t heinlein-test:latest . && docker run -v $HEINLEIN_TEST_DATA:/home/data $TEST_SET -it heinlein-test:latest $CMD
